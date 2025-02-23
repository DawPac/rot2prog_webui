from http.server import BaseHTTPRequestHandler, HTTPServer
import urllib.parse as urlparse
import rot2prog
import maidenhead
import json
from skyfield.api import load
from skyfield.iokit import parse_tle_file
from skyfield.api import wgs84
import time
import threading

hostName = "192.168.1.9"
serverPort = 8080
rotor = rot2prog.ROT2Prog("/dev/ttyUSB0")
max_days = 7.0         # download again once 7 days old
name = 'stations.tle'  # custom filename, not 'gp.php'
my_location = wgs84.latlon(+51.9751747, +20.1445221)
difference = None
base = 'https://celestrak.org/NORAD/elements/gp.php'
url = base + '?GROUP=amateur&FORMAT=tle'
track = False
if not load._exists(name) or load.days_old(name) >= max_days:
    load.download(url, filename=name)
ts = load.timescale()
with load.open('stations.tle') as f:
    satellites = list(parse_tle_file(f, ts))

print('Loaded', len(satellites), 'satellites')

class tracking(threading.Thread):
    def run(self,*args,**kwargs):
        while(track):
            t = ts.now()
            topocentric = difference.at(t)
            alt, az, distance = topocentric.altaz()
            if alt.degrees > -15:
                rotor.set(az.degrees, alt.degrees)
            else:
                rotor.set(az.degrees, 0)
            time.sleep(1)

class MyServer(BaseHTTPRequestHandler):
    def do_GET(self):
        global track
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        command = urlparse.parse_qs(urlparse.urlparse(self.path).query).get('command', None)
        az = urlparse.parse_qs(urlparse.urlparse(self.path).query).get('az', None)
        el = urlparse.parse_qs(urlparse.urlparse(self.path).query).get('el', None)
        if (command == ["set"]):
            track = False
            print("Rotor set to elevation: "+el[0]+", azimuth: "+az[0])
            rotor.set(float(az[0]),float(el[0]))
        elif (command == ["status"]):
            print("Rotor status read")
            self.wfile.flush()
            self.wfile.write(bytes('{"az": '+str(rotor.status()[0])+', "el": '+str(rotor.status()[1])+'}', "utf-8"))
        elif (command == ["sat"]):
            global difference
            track = False
            time.sleep(1)
            sat_name = urlparse.parse_qs(urlparse.urlparse(self.path).query).get('sat', None)
            by_name = {sat.name: sat for sat in satellites}
            satellite = by_name[sat_name[0]]
            difference = satellite - my_location
            print("Started tracking", satellite.name)
            track = True
            t = tracking()
            t.start()
        elif (command == ["locator"]):
            pass
        elif (command == ["country"]):
            pass
        else:
            self.wfile.flush()
            self.wfile.write(bytes("""
                                <!DOCTYPE html>
                                <html>
                                    <head>
                                    </head>
                                    <body>
                                        Azimuth: <input type="number", value="0", id="az"> Elevation: <input type="number", value="0", id="el">
                                        <button onclick='setStatus()'>Send</button>
                                        <button onclick='getStatus()'>Refresh</button>
                                        <select name="sat" id="sat">""", "utf-8"))
            for sat in satellites:
                self.wfile.write(bytes('<option value="'+sat.name+'">'+sat.name+"</option>", "utf-8"))
            self.wfile.write(bytes("""</select>
                                        <button onclick='trackSat()'>Track</button>
                                        <script>
                                            function setStatus(){
                                                var status = '';
                                                var az = document.getElementById('az').value;
                                                var el = document.getElementById('el').value;
                                                fetch('/?command=set&az='+az+'&el='+el)
                                            }
                                            async function getStatus() {
                                                let response = await fetch('/?command=status');
                                                let json = await response.json();
                                                document.getElementById('az').value = json.az;
                                                document.getElementById('el').value = json.el;
                                            }
                                            function trackSat() {
                                                var sat = document.getElementById('sat')
                                                console.log(sat.value)
                                                fetch('/?command=sat&sat='+sat.value)
                                            }
                                            window.onload = function() {
                                                getStatus();
                                            };
                                        </script>
                                    </body>
                                </html>
                                """, "utf-8"))
        

if __name__ == "__main__":
    webServer = HTTPServer((hostName, serverPort), MyServer)
    print("Server started http://%s:%s" % (hostName, serverPort))

    webServer.serve_forever()


    webServer.server_close()
    print("Server stopped.")
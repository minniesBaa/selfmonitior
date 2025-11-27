import truenas_api_client, json, yaml, pythonping
from flask import Flask
from flask_apscheduler import APScheduler
from flask_cors import CORS
import waitress

app = Flask(__name__)
CORS(app)

sh = APScheduler()
sh.init_app(app)
sh.start()

history = {}

serve = {}

test_counter = -1
prv = "if this got served something is very wrong"


def update_history(name, value):
    if name not in history.keys():
        history[name] = [2] * 1440
    del(history[name][0])
    history[name].append(value)
    return history[name]

def check_for_updates(l,k,ver):
    global test_counter, prv
    if test_counter % 1440 != 0:
        return prv
    try:
        res = {"updates_available": False, "app_updates": []}
        with truenas_api_client.Client(uri=f"wss://{l}/websocket", verify_ssl=False) as c:
            c.call("auth.login_with_api_key", k)
            app_updates = c.call("app.query")
            global updates
            if float(ver) < 25.10:
                updates = c.call("update.check_available")
                res["updates_available"] = True if updates["status"] == "AVAILABLE" else False #type: ignore
             
            if ver == "25.10":
                updates = c.call("update.status")
                if updates["status"]["new_version"]: # type: ignore
                    res["updates_available"] = True

            for i in app_updates: # type: ignore
                if i["upgrade_available"] == True:
                    res["app_updates"].append([i["name"]])

        prv = res
        return res
    except Exception as e:
        print(e)
        return {}

def collect():
    global test_counter
    test_counter += 1
    with open("config.yaml", "r") as f:
        servers = yaml.load(f.read(), yaml.Loader)["servers"]
    res = {}
    out = {}
    for server in servers:
        res = {}
        up = True
        updates = None
        if pythonping.ping(server["uri"], count=4, payload=b"Testing server status").packets_lost == 4:
            up = False
        if server["api_key"] != "none":
            updates = check_for_updates(server["uri"], server["api_key"], server["tn_ver"])
            if updates == {}:
                up = False
        res["updates"] = updates
        res["up"] = up
        res["history"] = update_history(server["name"], 1 if up else 0)
        out[server["name"]] = res
    global serve
    serve = out


sh.add_job(
    id='ping',
    func=collect,
    trigger='interval',
    seconds=60
)

@app.route("/get")
def get():
    return json.dumps(serve)

collect()

if __name__ == "__main__":
    waitress.serve(app, port=6067, host="0.0.0.0")
    pass
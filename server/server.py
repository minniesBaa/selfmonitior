import truenas_api_client, json, yaml, pythonping
from flask import Flask
from flask_apscheduler import APScheduler









history = {}

test_counter = -1
prv = "if this got served something is very wrong"


def update_history(name, value):
    if name not in history.keys():
        history[name] = [2] * 1440
    del(history[name][0])
    history[name].append(value)
    return history[name]

def check_for_updates(l,k):
    global test_counter, prv
    test_counter += 1
    if test_counter % 1440 != 0:
        return prv
    try:
        res = {"updates_available": False, "app_updates": {}}
        with truenas_api_client.Client(uri=f"wss://{l}/api/current", verify_ssl=False) as c:
            c.call("auth.login_with_api_key", k)
            updates = c.call("update.status")
            app_updates = c.call("app.query")
            if updates["status"]["new_version"]: # type: ignore
                res["updates_available"] = True
            for i in app_updates: # type: ignore
                if i["upgrade_available"] == True:
                    res["app_updates"][i["name"]] = True
                else:
                    res["app_updates"][i["name"]] = False
        prv = res
        return res
    except Exception as e:
        return {}

def collect():
    with open("config.yaml", "r") as f:
        servers = yaml.load(f.read(), yaml.Loader)["servers"]
    res = {}
    out = {}
    for server in servers:
        up = True
        updates = None
        if pythonping.ping(server["uri"], count=4, payload=b"Testing server status").packets_lost == 4:
            up = False
        if server["api_key"] != "none":
            updates = check_for_updates(server["uri"], server["api_key"])
            if updates == {}:
                up = False
        res["updates"] = updates
        res["up"] = up
        res["history"] = update_history(server["name"], 1 if up else 0)
        out[server["name"]] = res
    return out


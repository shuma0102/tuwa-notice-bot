import json, os

CONFIG_PATH = "config.json"
DEFAULT_COOLDOWN_SEC = 300

def load_config():
    if not os.path.exists(CONFIG_PATH):
        return {}
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_config(d):
    tmp = CONFIG_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)
    os.replace(tmp, CONFIG_PATH)

conf = load_config()

def get_guild_cfg(gid: int):
    g = conf.get(str(gid), {})
    g.setdefault("cooldown_sec", DEFAULT_COOLDOWN_SEC)
    g.setdefault("target_vc_ids", [])
    return g

def set_guild_cfg(gid: int, key: str, val):
    d = conf.get(str(gid), {})
    d[key] = val
    conf[str(gid)] = d
    save_config(conf)

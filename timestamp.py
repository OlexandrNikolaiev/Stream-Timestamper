import obspython as obs
import time
import datetime
import os
import urllib.request
import json

# Globals
log_file_path       = ""
hotkey_id           = obs.OBS_INVALID_HOTKEY_ID
start_time          = None
user_stream_title   = ""

# Credentials
twitch_user_login   = ""
twitch_client_id    = ""
twitch_oauth_token  = ""
youtube_api_key     = ""
youtube_channel_id  = ""
title_preference    = ""

def script_description():
    return (
        "Do not forget to set the 'Timestamp snap' hotkey.<br><br>"
        "If you are streaming to both Twitch and YouTube simultaneously, select the corresponding checkbox. "
        '<a href="https://github.com/OlexandrNikolaiev/Stream-Timestamper">Instructions</a>'
    )

def script_properties():
    props = obs.obs_properties_create()

    obs.obs_properties_add_path(props, "log_file", "Timestamp list location", obs.OBS_PATH_FILE_SAVE, "*.txt", None)
    obs.obs_properties_add_text(props, "stream_name", "Forced broadcast title \n(will be displayed in the list)", obs.OBS_TEXT_DEFAULT)


    obs.obs_properties_add_bool(props, "use_twitch", "Twitch Title Priority")

    obs.obs_properties_add_text(props, "twitch_user_login", "Twitch Login", obs.OBS_TEXT_DEFAULT)
    obs.obs_properties_add_text(props, "twitch_client_id", "Twitch Client ID", obs.OBS_TEXT_PASSWORD)
    obs.obs_properties_add_text(props, "twitch_oauth_token", "OAuth token", obs.OBS_TEXT_PASSWORD)

    obs.obs_properties_add_bool(props, "use_youtube", "YouTube Title Priority")
    obs.obs_properties_add_text(props, "youtube_api_key", "YouTube API Key", obs.OBS_TEXT_PASSWORD)
    obs.obs_properties_add_text(props, "youtube_channel_id", "YouTube Channel ID", obs.OBS_TEXT_PASSWORD)

    obs.obs_property_set_modified_callback(obs.obs_properties_get(props, "use_twitch"), on_twitch_radio_changed)
    obs.obs_property_set_modified_callback(obs.obs_properties_get(props, "use_youtube"), on_youtube_radio_changed)

    obs.obs_properties_add_button(props, "reset_timer", "                    Reset the timer manually                   ", reset_timer_callback)

    return props

def script_update(settings):
    global log_file_path, user_stream_title
    global twitch_user_login, twitch_client_id, twitch_oauth_token, youtube_api_key, youtube_channel_id

    log_file_path       = obs.obs_data_get_string(settings, "log_file")
    user_stream_title   = obs.obs_data_get_string(settings, "stream_name")
    twitch_user_login   = obs.obs_data_get_string(settings, "twitch_user_login")
    twitch_client_id    = obs.obs_data_get_string(settings, "twitch_client_id")
    twitch_oauth_token  = obs.obs_data_get_string(settings, "twitch_oauth_token")
    youtube_api_key     = obs.obs_data_get_string(settings, "youtube_api_key")
    youtube_channel_id  = obs.obs_data_get_string(settings, "youtube_channel_id")

def on_twitch_radio_changed(props, prop, settings):
    global title_preference
    if obs.obs_data_get_bool(settings, "use_twitch"):
        obs.obs_data_set_bool(settings, "use_youtube", False)
        title_preference = "twitch"
        #obs.script_log(obs.LOG_INFO, f"preference {title_preference}")
    return True

def on_youtube_radio_changed(props, prop, settings):
    global title_preference
    if obs.obs_data_get_bool(settings, "use_youtube"):
        obs.obs_data_set_bool(settings, "use_twitch", False)
        title_preference = "youtube"
        #obs.script_log(obs.LOG_INFO, f"preference {title_preference}")
    return True

def script_load(settings):
    global hotkey_id, start_time
    hotkey_id = obs.obs_hotkey_register_frontend(
        "stream_timestamp_hotkey",
        "Timestamp snap",
        on_hotkey
    )
    saved = obs.obs_data_get_array(settings, "hotkey_array")
    obs.obs_hotkey_load(hotkey_id, saved)
    obs.obs_data_array_release(saved)

    obs.obs_frontend_add_event_callback(frontend_event_callback)
    start_time = None

def script_defaults(settings):
    default = os.path.join(os.path.expanduser("~"), "stream_timestamps.txt")
    obs.obs_data_set_default_string(settings, "log_file", default)
    obs.obs_data_set_default_bool(settings, "use_youtube", True)

def script_save(settings):
    arr = obs.obs_hotkey_save(hotkey_id)
    obs.obs_data_set_array(settings, "hotkey_array", arr)
    obs.obs_data_array_release(arr)

def frontend_event_callback(event):
    global start_time
    if event == obs.OBS_FRONTEND_EVENT_STREAMING_STARTED:
        start_time = time.time()
        with open(log_file_path, "a", encoding="utf-8") as f:
            f.write("\n")
    elif event == obs.OBS_FRONTEND_EVENT_STREAMING_STOPPED:
        start_time = None

def on_hotkey(pressed):
    if pressed and obs.obs_frontend_streaming_active():
        record_timestamp()
    elif pressed:
        obs.script_log(obs.LOG_WARNING, "Stream is not live — timestamp not recorded")

def reset_timer_callback(props, prop):
    global start_time, log_file_path
    start_time = time.time()
    try:
        with open(log_file_path, "a", encoding="utf-8") as f:
            f.write("Timer was manually reset\n")
    except:
        pass
    return True

def fetch_youtube_title():
    if not youtube_api_key or not youtube_channel_id:
        return ""
    try:
        url = (
            "https://www.googleapis.com/youtube/v3/search"
            f"?part=snippet&channelId={youtube_channel_id}"
            "&eventType=live&type=video"
            f"&key={youtube_api_key}"
        )
        resp = urllib.request.urlopen(url)
        data = json.load(resp)
        items = data.get("items", [])
        if items:
            return "[Youtube] " + items[0]["snippet"]["title"]
    except Exception as e:
        obs.script_log(obs.LOG_WARNING, f"YouTube API error: {e}")
    return ""

def fetch_twitch_title():
    if not twitch_client_id or not twitch_oauth_token or not twitch_user_login:
        #obs.script_log(obs.LOG_INFO, "no twitch credentials")
        return ""
    try:
        url = f"https://api.twitch.tv/helix/streams?user_login={twitch_user_login}"
        req = urllib.request.Request(url)
        req.add_header("Client-ID", twitch_client_id)
        req.add_header("Authorization", f"Bearer {twitch_oauth_token}")
        
        with urllib.request.urlopen(req) as resp:
            data = json.load(resp)
            streams = data.get("data", [])
            if streams:
                #obs.script_log(obs.LOG_INFO, streams[0]["title"])
                return streams[0]["title"]
    except Exception as e:
        obs.script_log(obs.LOG_WARNING, f"Twitch API error: {e}")
    return ""

def record_timestamp():
    global start_time, user_stream_title, title_preference
    if start_time is None:
        start_time = time.time()

    elapsed = time.time() - start_time
    hh = int(elapsed // 3600)
    mm = int(elapsed // 60) % 60
    ss = int(elapsed % 60)

    ts = f"{hh:02d}:{mm:02d}:{ss:02d}"
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    title = ""
    if user_stream_title and user_stream_title.strip():
        title = user_stream_title.strip()
    elif all([twitch_user_login, twitch_client_id, twitch_oauth_token, youtube_api_key, youtube_channel_id]):
        if title_preference == "twitch":
            #obs.script_log(obs.LOG_INFO, f"{title_preference} preference")
            title = fetch_twitch_title()
        elif title_preference == "youtube":
            #obs.script_log(obs.LOG_INFO, f"{title_preference} preference")
            title = fetch_youtube_title()

    if not title:
        title = fetch_twitch_title()
        if not title:
            title = fetch_youtube_title()
            if not title:        
                #obs.script_log(obs.LOG_INFO, "Missing credentials")
                title = "Unknown"

    line = f"{title} | {now} | {ts}\n"
    try:
        with open(log_file_path, "a", encoding="utf-8") as f:
            f.write(line)
    except:
        pass

def script_unload():
    pass
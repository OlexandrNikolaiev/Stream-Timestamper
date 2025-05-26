import obspython as obs
import time
import datetime
import os
import urllib.request
import json

log_file_path         = ""
hotkey_id             = obs.OBS_INVALID_HOTKEY_ID
start_time            = None
user_stream_name      = ""
youtube_api_key       = ""
youtube_channel_id    = ""

def script_description():
    return ("Records stream timestamps to a file when the 'Timestamp snap' hotkey is pressed. To fetch the stream title, an API key and a channel ID are required. \n(See instructions for details.)")

def script_properties():
    props = obs.obs_properties_create()
    obs.obs_properties_add_path(
        props, "log_file", "Timestamp list location",
        obs.OBS_PATH_FILE_SAVE, "*.txt", None
    )
    obs.obs_properties_add_text(
        props, "stream_name", "Forced broadcast title (will be displayed in the list)", obs.OBS_TEXT_DEFAULT
    )
    obs.obs_properties_add_text(
        props, "youtube_api_key", "YouTube API Key", obs.OBS_TEXT_PASSWORD
    )
    obs.obs_properties_add_text(
        props, "youtube_channel_id", "YouTube Channel ID", obs.OBS_TEXT_PASSWORD
    ) # todo twitch
    obs.obs_properties_add_button(
        props, "reset_timer", "Reset the timer manually", reset_timer_callback
    )
    return props

def script_update(settings):
    global log_file_path, user_stream_name, youtube_api_key, youtube_channel_id
    log_file_path      = obs.obs_data_get_string(settings, "log_file")
    user_stream_name   = obs.obs_data_get_string(settings, "stream_name")
    youtube_api_key    = obs.obs_data_get_string(settings, "youtube_api_key")
    youtube_channel_id = obs.obs_data_get_string(settings, "youtube_channel_id")

def script_defaults(settings):
    default = os.path.join(os.path.expanduser("~"), "stream_timestamps.txt")
    obs.obs_data_set_default_string(settings, "log_file", default)

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

def script_save(settings):
    arr = obs.obs_hotkey_save(hotkey_id)
    obs.obs_data_set_array(settings, "hotkey_array", arr)
    obs.obs_data_array_release(arr)

def frontend_event_callback(event):
    global start_time
    if event == obs.OBS_FRONTEND_EVENT_STREAMING_STARTED:
        start_time = time.time()
        obs.script_log(obs.LOG_INFO, "Stream started, timer reset")
        with open(log_file_path, "a", encoding="utf-8") as f:
            f.write("\n")
    elif event == obs.OBS_FRONTEND_EVENT_STREAMING_STOPPED:
        start_time = None
        obs.script_log(obs.LOG_INFO, "Stream stopped, timer reset") 
        

def on_hotkey(pressed):
    if pressed:
        if obs.obs_frontend_streaming_active():
            record_timestamp()
        else:
            obs.script_log(obs.LOG_WARNING, "Stream is not live — timestamp not recorded") #todo

def reset_timer_callback(props, prop):
    global start_time
    start_time = time.time()
    obs.script_log(obs.LOG_INFO, "Timer manually reset")
    return True

def record_timestamp():
    global start_time, user_stream_name
    if start_time is None:
        start_time = time.time()
    elapsed = time.time() - start_time
    ss = int(elapsed % 60)
    hh = int(elapsed // 3600)
    mm = int(elapsed // 60)

    ts = f"{hh:02d}:{mm:02d}:{ss:02d}"

    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    #forced title
    if user_stream_name and user_stream_name.strip():
        name = user_stream_name.strip()
    else:
        name = ""
        if youtube_api_key and youtube_channel_id:
            try:
                url = ("https://www.googleapis.com/youtube/v3/search"
                       f"?part=snippet&channelId={youtube_channel_id}"
                       "&eventType=live&type=video"
                       f"&key={youtube_api_key}")
                resp = urllib.request.urlopen(url)
                data = json.load(resp)
                items = data.get("items", [])
                if items:
                    name = items[0]["snippet"]["title"]
            except Exception as e:
                obs.script_log(obs.LOG_WARNING,
                               f"YouTube API error: {e}")
        if not name:
            try:
                name = obs.obs_frontend_get_current_profile() or ""
            except:
                name = ""
        # last resort - date
        if not name:
            name = now.split(" ")[0]

    line = f"{name} | {now} | {ts}\n"
    try:
        with open(log_file_path, "a", encoding="utf-8") as f:
            f.write(line)
        obs.script_log(obs.LOG_INFO, f"Recorded: {line.strip()}")
    except Exception as e:
        obs.script_log(obs.LOG_ERROR, f"Recording error: {e}")

def script_unload():
    pass

"""Support to interface with the hadora Web API."""
import logging
import re

from datetime import timedelta
import requests
import json
import voluptuous as vol

from homeassistant.components.media_player import PLATFORM_SCHEMA, MediaPlayerEntity
from homeassistant.components.media_player.const import (
    MEDIA_TYPE_MUSIC,
    SUPPORT_CLEAR_PLAYLIST,
    SUPPORT_NEXT_TRACK,
    SUPPORT_PAUSE,
    SUPPORT_PLAY,
    SUPPORT_PREVIOUS_TRACK,
    SUPPORT_SEEK,
    SUPPORT_SELECT_SOURCE,
    SUPPORT_SHUFFLE_SET,
    SUPPORT_STOP,
    SUPPORT_VOLUME_MUTE,
    SUPPORT_VOLUME_SET,
)
from homeassistant.const import (
    CONF_HADORA_UID,
    CONF_NAME,
    CONF_HADORA_PWD,
    STATE_IDLE,
    STATE_OFF,
    STATE_PAUSED,
    STATE_PLAYING,
    STATE_UNAVAILABLE,
)
import homeassistant.helpers.config_validation as cv
import homeassistant.util.dt as dt_util
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "hadora"
DEFAULT_PORT = 3333

SUPPORT_hadora = (
    SUPPORT_PAUSE
    | SUPPORT_VOLUME_SET
    | SUPPORT_VOLUME_MUTE
    | SUPPORT_PREVIOUS_TRACK
    | SUPPORT_NEXT_TRACK
    | SUPPORT_SEEK
    | SUPPORT_STOP
    | SUPPORT_PLAY
    | SUPPORT_SELECT_SOURCE
    | SUPPORT_SHUFFLE_SET
    | SUPPORT_CLEAR_PLAYLIST
)

PLAYLIST_UPDATE_INTERVAL = timedelta(seconds=15)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(""): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional("", default=DEFAULT_PORT): cv.port,
    }
)

def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the hadora platform."""
    name = config.get(CONF_NAME)
    host = config.get("")
    port = config.get("")

    add_entities([HAdora(name, host, port, hass)], True)

class HAdora(MediaPlayerEntity):
    """HAdora Player Object."""

    def __init__(self, name, host, port, hass):
        """Initialize the media player."""
        self.host = host
        self.port = port
        self.hass = hass
        self._url = "{}:{}".format(host, str(port))
        self._name = name
        self._available = False

        self._hadora = None
        self._coverurl = {}
        self._playinfo = {}
        self._playlists = []
        self._playlists_db = dict()
        self._currentplaylist = None

        self._state = STATE_UNAVAILABLE
        self._state_dict = {}
        self._media_position = int()
        self._media_position_dict = {}
        self._media_position_updated_at = None
        self._volume_level = {}
        self._shuffle = {}
        self._is_volume_muted = {}

    def send_hadora_msg(self, method, params):
        """Send message."""
        try:
            url = f"http://{self._url}/RPC_JSON"
            payload = {"version": "1.1", "method": method, "id": 1, "params": params}
            response = requests.post(url, json=payload, timeout=3)
            if response.status_code == 200:
                try:
                    data = response.json()
                    result = data["result"]
                except:
                    result = None
            else:
                _LOGGER.error(
                    "Query failed, response code: %s Full message: %s",
                    response.status_code,
                    response,
                )
                return False

        except requests.exceptions.RequestException:
            _LOGGER.error(
                "Could not send command %s to hadora at: %s", method, self._url
            )
            return False
        try:
            return result
        except AttributeError:
            _LOGGER.error("Received invalid response: %s", data)
            return False

    def update(self):
        """Update state."""
        if self._hadora is None:
            try:
                url = f"http://{self._url}/RPC_JSON"
                payload = {"version":"1.1","method":"Status","id":1,"params":{"status_id":4}}
                response = requests.post(url, json=payload, timeout=3)
                if response.status_code == 200:
                    self._available = True
                    self.update_playinfo()
                    self.update_coverurl()
                    self.update_state()
                    self.update_media_position()
                    self.update_volume_level()
                    self.update_shuffle()
                    self.update_is_volume_muted()
                    self.update_playlists()
                    
            except requests.exceptions.RequestException:
                if self._available:
                    _LOGGER.error(
                        "Connect error to hadora at: %s", self._url
                    )
                    self._available = False
                self._hadora = None
                return

            self._state = STATE_IDLE
            self._available = True

    def update_playinfo(self):
        resp = self.send_hadora_msg("GetPlaylistEntryInfo", {"playlist_id": -1, "track_id": -1})
        if resp is False:
            return
        self._playinfo = resp.copy()

    def update_coverurl(self):
        resp = self.send_hadora_msg("GetCover", {"playlist_id": -1, "track_id": -1, "cover_width": 512, "cover_height": 512})
        if resp is False:
            return
        elif resp is None:
            self._coverurl = {}
        else:
            self._coverurl = resp.copy()

    def update_state(self):
        resp = self.send_hadora_msg("Status", {"status_id":4})
        if resp is False:
            return
        self._state_dict = resp.copy()

    def update_media_position(self):
        resp = self.send_hadora_msg("Status", {"status_id":31})
        if resp is False:
            return
        self._media_position_dict = resp.copy()

    def update_volume_level(self):
        resp = self.send_hadora_msg("Status", {"status_id":1})
        if resp is False:
            return
        self._volume_level = resp.copy()

    def update_shuffle(self):
        resp = self.send_hadora_msg("Status", {"status_id":41})
        if resp is False:
            return
        self._shuffle = resp.copy()

    def update_is_volume_muted(self):
        resp = self.send_hadora_msg("Status", {"status_id":5})
        if resp is False:
            return
        self._is_volume_muted = resp.copy()

    @property
    def media_content_type(self):
        """Content type of current playing media."""
        return MEDIA_TYPE_MUSIC

    @property
    def state(self):
        """Return the state of the device."""
        playback_state = self._state_dict.get("value", None)
        if playback_state == 2:
            return STATE_PAUSED
        if playback_state == 1:
            return STATE_PLAYING
        return STATE_IDLE

    @property
    def available(self):
        """Return True if entity is available."""
        return self._available

    @property
    def media_title(self):
        """Title of current playing media."""
        return self._playinfo.get("title", None)

    @property
    def media_artist(self):
        """Artist of current playing media (Music track only)."""
        return self._playinfo.get("artist", None)

    @property
    def media_album_name(self):
        """Artist of current playing media (Music track only)."""
        return self._playinfo.get("album", None)

    @property
    def media_image_url(self):
        """Image url of current playing media."""
        url = self._coverurl.get("album_cover_uri", None)
        if url is None:
            return None
        if str(url[0:2]).lower() == "ht":
            mediaurl = url
        else:
            mediaurl = f"http://{self.host}:{self.port}/{url}"
        return mediaurl

    @property
    def media_position(self):
        """Time in seconds of current seek position."""
        time = self._media_position_dict.get("value")
        if time is None:
            return None
        return int(time)

    @property
    def media_position_updated_at(self):
        """When was the position of the current playing media valid."""
        time = dt_util.utcnow()
        return time

    @property
    def media_duration(self):
        """Time in seconds of current song duration."""
        time = self._playinfo.get("duration")
        if time is None:
            return None

        return int(time) // 1000

    @property
    def volume_level(self):
        """Volume level of the media player (0..1)."""
        volume = self._volume_level.get("value", None)
        if volume is not None and volume != "":
            volume = int(volume) / 100
        return volume

    @property
    def is_volume_muted(self):
        """Boolean if volume is currently muted."""
        return self._is_volume_muted.get("value", 0) == 1

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def shuffle(self):
        """Boolean if shuffle is enabled."""
        return self._shuffle.get("value", 0) == 1

    @property
    def source_list(self):
        """Return the list of available input sources."""
        return self._playlists

    @property
    def source(self):
        """Name of the current input source."""
        playlistid = self._playinfo.get("playlist_id", None)
        playlistname = self._playlists_db[str(playlistid)]
        self._currentplaylist = playlistname
        return self._currentplaylist

    @property
    def supported_features(self):
        """Flag of media commands that are supported."""
        return SUPPORT_hadora

    def media_next_track(self):
        """Send media_next command to media player."""
        self.send_hadora_msg("PlayNext", "{}")

    def media_previous_track(self):
        """Send media_previous command to media player."""
        self.send_hadora_msg("PlayPrevious", "{}")

    def media_play(self):
        """Send media_play command to media player."""
        self.send_hadora_msg("Play", "{}")

    def media_pause(self):
        """Send media_pause command to media player."""
        self.send_hadora_msg("Pause", "{}")

    def media_stop(self):
        """Send media_pause command to media player."""
        self.send_hadora_msg("Stop", "{}")

    def set_volume_level(self, volume):
        """Send volume_up command to media player."""
        self.send_hadora_msg("Status", {"status_id": 1, "value": int(volume * 100)})

    def mute_volume(self, mute):
        """Send mute command to media player."""
        mutecmd = 1 if mute else 0
        self.send_hadora_msg("Status", {"status_id": 5, "value": mutecmd })
   
    def set_shuffle(self, shuffle):
        """Enable/disable shuffle mode."""
        shufflecmd = 1 if shuffle else 0
        self.send_hadora_msg("Status", {"status_id": 5, "value": shufflecmd })
        
    def media_seek(self, position):
        """Send seek command."""
        self.send_hadora_msg("Status", {"status_id": 31, "value": int(position) })

    def select_source(self, source):
        """Choose a different available playlist and play it."""
        self._currentplaylist = source
        
        def get_key(val):
            for key, value in self._playlists_db.items():
                 if val == value:
                     return key
            return "key doesn't exist"

        playlistid = get_key(source)
        resp = self.send_hadora_msg("GetPlaylistEntries", {"playlist_id":int(playlistid),"fields":["album","artist","bitrate","genre","duration","filesize","date","id","rating"]})
        try: 
            entries = resp.get("entries")
        except:
            _LOGGER.error("Received invalid response: resp: %s", resp,)
            return False
            
        try:
            trackinfo = list(entries[0])
        except:
            _LOGGER.error("Received invalid response: : entries: %s", entries,)
            return False
            
        try:
            trackid = trackinfo[7]
        except:
            _LOGGER.error("Received invalid response: trackinfo: %s", trackinfo,)
            return False

        resp2 = self.send_hadora_msg("Play", {"playlist_id": int(playlistid), "track_id": int(trackid)})
        if resp2 is False:
            return
        
    def clear_playlist(self):
        """Clear players playlist."""
        self._currentplaylist = None
        self.send_hadora_msg("Stop", "{}")

    @Throttle(PLAYLIST_UPDATE_INTERVAL)
    def update_playlists(self, **kwargs):
        """Update available hadora playlists."""
        playlists = self.send_hadora_msg(
            "GetPlaylists", "{fields: [\"id\", \"title\", \"crc32\"]}}"
        )
        self._playlists = re.findall(r"'title': '(.+?)'", str(playlists))
        
        playlists_db = re.findall(r"'id': (.+?), 'title': '(.+?)'", str(playlists))
        for var in playlists_db:
            self._playlists_db[var[0]] = var[1]

        # _LOGGER.debug(
        #     "Success! self._playlists_db: %s",
        #     self._playlists_db,
        # )

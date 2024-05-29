# ha_dora
Custom component for Home Assistant to control Pandora, originally forked from [hadora_uid](https://github.com/xilense/aimp_custom_component) 

# screenshot


# dependencies




# manual installation
1. Using the tool of choice open the directory (folder) for your HA configuration (where you find `configuration.yaml`).
2. If you do not have a `custom_components` directory (folder) there, you need to create it.
3. In the `custom_components` directory (folder) create a new folder called `aimp`.
4. Download [\_\_init__.py](https://github.com/xilense/aimp_custom_component/blob/master/__init__.py), [manifest.json](https://github.com/xilense/aimp_custom_component/blob/master/manifest.json), [media_player.py](https://github.com/xilense/aimp_custom_component/blob/master/media_player.py) in this repository.
5. Place the files you downloaded in the new directory (folder) you created.
6. Add aimp to media_player config and Restart Home Assistant.

# yaml config 
```
media_player:
  - platform: aimp
    name: 'AIMP'
    host: !secret aimp_ip
    port: 3333
```

# to-do
* Add browse_media

# aid-cross-compat-tool
allows converting of ai dungeon content to novelai .scenario and vice versa. also known as AIDCCT/AID-CCT/it's not AIDCAT please don't get them mixed up

## how to use
* make sure you have the right modules installed. i wrote this in python 3.9 so if you're sure you have everything installed but you're using a different python version that might be the issue
* make a .env file in the repo's folder that looks like: `xaccess = "x-access-token-goes-here-lol"`
* set `xaccess` to your AID account's x-access token, found in the request headers tab when viewing any JSON formatted request on the AID site. **this may get deprecated in the future so when that happens i'll have to rewrite the bit of code to do auth, but until i do the program won't work.**
* launch run.py and you're good to go

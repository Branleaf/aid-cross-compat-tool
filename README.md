# aid-cross-compat-tool
allows converting of ai dungeon content to novelai .scenario and vice versa. also known as AIDCCT/AID-CCT/it's not AIDCAT please don't get them mixed up

i made this for a latitude hackathon and fixed (worked around) a bug with adventure to .story conversion that would cause them to basically brick your NAI account if you tried to import them. instead of converting AID adventures to stories it currently just supports converting them to .scenario files. still retains all of their actions (up to 50k to avoid blowing up aid servers), but won't show a visual difference between ai and player text

## how to use
* make sure you have the right modules installed. i wrote this in python 3.9 so if you're sure you have everything installed but you're using a different python version that might be the issue
* make a .env file in the repo's folder that looks like: `xaccess = "x-access-token-goes-here-lol"`
* set `xaccess` to your AID account's x-access token, found in the request headers tab when viewing any JSON formatted request on the AID site. **this may get deprecated in the future so when that happens i'll have to rewrite the bit of code to do auth, but until i do the program won't work.**
* launch run.py and you're good to go

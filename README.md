# aid-cross-compat-tool
allows converting of ai dungeon content to novelai .scenario and vice versa. also known as AIDCCT/AID-CCT/it's not AIDCAT please don't get them mixed up

i made this for a latitude hackathon and fixed (worked around) a bug with adventure to .story conversion that would cause them to basically brick your NAI account if you tried to import them. that doesn't happen any more but there are _some_ things that i can't really do much about - those are detailed further down though

## how to use
* make sure you have the right modules installed. i wrote this in python 3.9 so if you're sure you have everything installed but you're using a different python version that might be the issue
* make a .env file in the repo's folder that looks like: `xaccess = "x-access-token-goes-here-lol"`
* set `xaccess` to your AID account's x-access token, found in the request headers tab when viewing any JSON formatted request on the AID site. **this may get deprecated in the future so when that happens i'll have to rewrite the bit of code to do auth, but until i do the program won't work.**
* launch run.py and you're good to go

## known issues/limitations
* you have to own the scenario/adventure you want to export. this is an AID API thing - can't see the memory/AN/WI of a scenario you don't own from the view screen unfortunately. **workaround:** start an adventure from the published scenario you want to export, undo the action the ai generates and export that adventure instead.
* you can't just copy-paste the link of a scenario with scenario options and have it export into a .scenario. **workaround:** go into the scenario edit screen on the option you want to export, get the publicid from the url and slap it on the end of the `https://play.aidungeon.io/main/scenarioView?publicId=` link. or do the same workaround from the above point, that'll work too.
* you can only export adventures up to 50k actions long. **workaround:** just change the `limit` in the API request if you absolutely have to export a bigger adventure. i just set it to that to lower risk of timing out on big requests.
* you can't import novelai stories to AID adventures. this is because when creating an adventure or adding an action in AID through the API, it _always_ generates something, and requires a base scenario to start from - even if it's the "custom" option. i don't think there's a workaround for this, unfortunately
* the commandline window is open behind the actual GUI. that's just because i've never tried to remove it and don't know how to with pysimplegui to be honest

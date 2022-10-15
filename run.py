import PySimpleGUI as sg
import json, requests, os, re, logging
from dotenv import load_dotenv
from transformers import GPT2TokenizerFast
# so it doesn't warn about the tokenizer tokenizing something too long for a model we aren't planning to feed anything to
logging.getLogger("transformers.tokenization_utils_base").setLevel(logging.ERROR)

tokenizer = GPT2TokenizerFast.from_pretrained("gpt2")

# AID API functionality
load_dotenv()
# auth is completely different now, woo.
user_email = os.getenv("email")
user_pass = os.getenv("password")
auth_url = "https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key=AIzaSyBJJSL9pvAZ4llQWavd565hXGrCpHppJj8"
url = "http://api.aidungeon.io/graphql"
headers = {
    'content-type': 'application/json'
}

def fetch_firebase_token():
    resp = requests.post(auth_url, f'{{"returnSecureToken":true,"email":{json.dumps(user_email)},"password":{json.dumps(user_pass)}}}', headers = headers)
    # convert response to json so i can actually read the token
    json_resp = resp.json()
    # and add the received token to the headers for the AID API requests to use
    headers.update({"authorization":f"firebase {json_resp['idToken']}"})

def fetch_scenario(publicid:str):
    resp = requests.post(url, f'{{"operationName":"ScenarioEditScreenGetScenario","variables":{{"publicId":{json.dumps(publicid)}}},"query":"query ScenarioEditScreenGetScenario($publicId: String) {{ scenario(publicId: $publicId) {{ ...ScenarioEditScenario }}}}fragment ScenarioEditScenario on Scenario {{description memory authorsNote prompt tags title options {{publicId}}}}"}}', headers = headers)
    json_resp = resp.json()
    #print(json_resp)
    if "errors" in json_resp.keys():
        return None
    else:
        return json_resp['data']['scenario']

def fetch_adventure(publicid:str):
    resp = requests.post(url, f'{{"operationName":"AdventureViewScreenGetAdventure","variables":{{"publicId":{json.dumps(publicid)},"limit":50000,"offset":0,"desc":false}},"query":"query AdventureViewScreenGetAdventure($publicId: String, $limit: Int, $offset: Int, $desc: Boolean) {{ adventure(publicId: $publicId) {{ actionCount actionWindow(limit: $limit, offset: $offset, desc: $desc) {{ text }} ...ContentHeadingSearchable }}}}fragment ContentHeadingSearchable on Searchable {{ title description tags }}"}}', headers = headers)
    json_resp = resp.json()
    #print(json_resp)
    if "errors" in json_resp.keys():
        return None
    else:
        return json_resp['data']['adventure']

def fetch_adventure_extras(publicid:str):
    # gets memory/AN from an adventure
    resp = requests.post(url, f'{{"operationName":"ActionContextGetAdventureAction","variables":{{"publicId":{json.dumps(publicid)}}},"query":"query ActionContextGetAdventureAction($publicId: String) {{ adventure(publicId: $publicId) {{memory authorsNote}}}}"}}', headers = headers)
    json_resp = resp.json()
    if "errors" in json_resp.keys():
        return None, json_resp['errors']
    else:
        return json_resp['data']['adventure']['memory'], json_resp['data']['adventure']['authorsNote']

def fetch_world_info(publicid:str, type:str):
    resp = requests.post(url, f'{{"operationName":"WorldInfoManagerContextGetWorldInfo","variables":{{"type":"Active","page":0,"match":"","pageSize":900,"contentPublicId":{json.dumps(publicid)},"contentType":"{type}","filterUnused":false}},"query":"query WorldInfoManagerContextGetWorldInfo($type: String, $page: Int, $match: String, $pageSize: Int, $contentPublicId: String, $contentType: String, $filterUnused: Boolean) {{ worldInfoType(type: $type, page: $page, match: $match, pageSize: $pageSize, contentPublicId: $contentPublicId, contentType: $contentType, filterUnused: $filterUnused) {{description name keys entry}}}}"}}', headers = headers)
    json_resp = resp.json()
    #print(json_resp)
    return json_resp['data']['worldInfoType']

# scenario loading functions
def assemble_from_aid_scenario(scenario, worldinfo):
    scenario.setdefault("tags", [])
    if scenario['memory'] is None: scenario['memory'] = ""
    if scenario['authorsNote'] is None: scenario['authorsNote'] = ""
    # adventure?
    if "actionCount" in scenario:
        scenario['type'] = "adventure"
        scenario['actionWindow'].reverse()
        scenario['prompt'] = ""
        for x in range(len(scenario['actionWindow'])):
            scenario['prompt'] += scenario['actionWindow'][x]['text']
    else:
        scenario['type'] = "scenario"
        scenario['actionWindow'] = None
    # put together
    assembled_scen = {
    "title": scenario['title'],
    "origin": "AI Dungeon",
    "description": scenario['description'],
    "prompt": scenario['prompt'],
    "memory": scenario['memory'],
    "authorsnote": scenario['authorsNote'],
    "worldinfo": worldinfo,
    "tags": scenario['tags'],
    "type": scenario['type'],
    "actions": scenario['actionWindow']
    }
    return assembled_scen

def assemble_wi_from_aid(worldinfo):
    new_wi = []
    for x in range(len(worldinfo)):
        # NONE of these fields are guaranteed to even be there. i have to check each WI entry to see if either description or keys exist, or BOTH.
        entry = {"name": None, "keys": None, "entry": None}
        # convert keys to a list of keys... or use the WI name as a key if there are no keys
        if worldinfo[x]['keys'] is not None:
            # split at commas to make a list
            worldinfo[x]['keys'] = worldinfo[x]['keys'].split(",")
            # then get rid of leading/trailing whitespace because that's just how keys are written in AID
            for key in range(len(worldinfo[x]['keys'])):
                worldinfo[x]['keys'][key] = worldinfo[x]['keys'][key].strip()
        else:
            worldinfo[x]['keys'] = [worldinfo[x]['name']]
        entry['keys'] = worldinfo[x]['keys']
        # get WI name... or use the first key if there isn't a name
        if worldinfo[x]['name'] is not None:
            entry['name'] = worldinfo[x]['name']
        else:
            entry['name'] = worldinfo[x]['keys'][0]
        # get WI entry... or use WI description if there isn't an entry
        if worldinfo[x]['entry'] is not None:
            entry['entry'] = worldinfo[x]['entry']
        else:
            entry['entry'] = worldinfo[x]['description']
        new_wi.append(entry)
    return new_wi

def count_tokens(text):
    tokens = tokenizer.encode(text, truncation = False)
    return len(tokens)

def display_tags(tags:list):
    tagstring = ""
    if tags:
        for t in range(len(tags)):
            tagstring += f" [{tags[t]}]"
        tagstring = tagstring.lstrip()
    if not tagstring: tagstring = "(no tags)"
    return tagstring

def fetch_nai_scenario(filepath:str):
    with open(filepath, "rb") as f:
        data = json.load(f)
    return data

def assemble_from_nai_scenario(data, worldinfo):
    assembled_scen = {
        "title": data['title'],
        "origin": "NovelAI",
        "description": data['description'],
        "prompt": data['prompt'],
        "memory": data['context'][0]['text'],
        "authorsnote": data['context'][1]['text'],
        "worldinfo": worldinfo,
        "tags": data['tags'],
        "type": "scenario",
        "actions": None
        }
    return assembled_scen

def assemble_wi_from_nai(data):
    worldinfo = data['lorebook']['entries']
    new_wi = []
    for x in range(len(worldinfo)):
        # if there's no name for it, just set it to key #1
        if not worldinfo[x]['displayName']: worldinfo[x]['displayName'] = worldinfo[x]['keys'][0]
        new_wi.append({"name": worldinfo[x]['displayName'], "keys": worldinfo[x]['keys'], "entry": worldinfo[x]['text']})
    return new_wi

# conversion/exporting functions
def convert_wi_to_nai(worldinfo):
    nai_wi = []
    for x in range(len(worldinfo)):
        nai_wi.append({
            "text": worldinfo[x]['entry'],
            "displayName": worldinfo[x]['name'],
            "keys": worldinfo[x]['keys'],
            "searchRange": 1000,
            "enabled": True,
            "forceActivation": False,
            "keyRelative": False,
            "nonStoryActivatable": False,
            "category": "",
            "loreBiasGroups": []
            })
    return nai_wi     

def assemble_nai_scenario(scenario):
    # check if things are blank. this crashes the site if you upload null stuff lol
    if scenario['title'] is None: scenario['title'] = ""
    if scenario['prompt'] is None: scenario['prompt'] = ""
    if scenario['authorsnote'] is None: scenario['authorsnote'] = ""
    if scenario['memory'] is None: scenario['memory'] = ""
    if scenario['description'] is None: scenario['description'] = ""
    # pack yer bags
    nai_scen = {
  "scenarioVersion": 2,
  "title": scenario['title'],
  "description": scenario['description'],
  "prompt": scenario['prompt'],
  "tags": scenario['tags'],
  "context": [
    {
      "text": scenario['memory'],
      "contextConfig": {
        "prefix": "",
        "suffix": "\n",
        "tokenBudget": 2048,
        "reservedTokens": 0,
        "budgetPriority": 800,
        "trimDirection": "trimBottom",
        "insertionType": "newline",
        "maximumTrimType": "sentence",
        "insertionPosition": 0
      }
    },
    {
      "text": scenario['authorsnote'],
      "contextConfig": {
        "prefix": "",
        "suffix": "\n",
        "tokenBudget": 2048,
        "reservedTokens": 2048,
        "budgetPriority": -400,
        "trimDirection": "trimBottom",
        "insertionType": "newline",
        "maximumTrimType": "sentence",
        "insertionPosition": -4
      }
    }
  ],
  "ephemeralContext": [],
  "placeholders": [],
  "settings": {
    "model": "euterpe-v2"
  },
  "lorebook": {
    "lorebookVersion": 4,
    "entries": scenario['worldinfo'],
    "settings": {
      "orderByKeyLocations": False
    },
    "categories": []
  },
  "author": "",
  "storyContextConfig": {
    "prefix": "",
    "suffix": "",
    "tokenBudget": 2048,
    "reservedTokens": 512,
    "budgetPriority": 0,
    "trimDirection": "trimTop",
    "insertionType": "newline",
    "maximumTrimType": "sentence",
    "insertionPosition": -1,
    "allowInsertionInside": True
  },
  "contextDefaults": {
    "ephemeralDefaults": [],
    "loreDefaults": []
  },
  "phraseBiasGroups": [],
  "bannedSequenceGroups": [
    {
      "sequences": [],
      "enabled": True
    }
  ]
}
    return nai_scen

def export_converted_nai_scenario(scenario):
    filename = re.sub("([^A-Za-z 0-9-()}{_.,])", "_", scenario['title'])
    with open(f"{filename}.scenario", "w+", encoding = "utf8") as f:
        json.dump(scenario, f)
    return filename

def build_nai_action_window(actions):
    datablocks = []
    datafragments = []
    text_length = 0
    datablocks.append({
          "nextBlock": [
            1
          ],
          "prevBlock": -1,
          "origin": "root",
          "startIndex": 0,
          "endIndex": 0,
          "dataFragment": {
            "data": "",
            "origin": "root"
          },
          "fragmentIndex": -1,
          "removedFragments": [],
          "chain": False
        })
    datafragments.append({
            "data": "",
            "origin": "root"
            })
    for a in range(len(actions)):
        # determine origin
        if a == 1: origin = "prompt"
        elif ">" in actions[a]['text'][:3]: origin = "user"
        else: origin = "ai"
        # add datablock
        if a == 0: prevblock = 0
        else: prevblock = a-1
        datablocks.append({
            "nextBlock": [a+1],
            "prevBlock": prevblock,
            "origin": origin,
            "startIndex": text_length,
            "endIndex": text_length+len(actions[a]['text']),
            "dataFragment": {
                "data": actions[a]['text'],
                "origin": origin
            },
            "fragmentIndex": a,
            "removedFragments": [],
            "chain": False
            })
        # add datafragment. this is referenced outside of the above dataFragment section so i want to return it seperately
        datafragments.append({
            "data": actions[a]['text'],
            "origin": origin
            })
        text_length += len(actions[a]['text'])
    return datablocks, datafragments

def export_converted_nai_story(adventure):
    filename = re.sub("([^A-Za-z 0-9-()}{_.,])", "_", adventure['metadata']['title'])
    with open(f"{filename}.story", "w+", encoding = "utf8") as f:
        json.dump(adventure, f)
    return filename

def assemble_nai_story(adventure):
    if adventure['title'] is None: adventure['title'] = ""
    if adventure['prompt'] is None: adventure['prompt'] = ""
    if adventure['authorsnote'] is None: adventure['authorsnote'] = ""
    if adventure['memory'] is None: adventure['memory'] = ""
    if adventure['description'] is None: adventure['description'] = ""
    adventure['actions'], adventure['actionfragments'] = build_nai_action_window(adventure['actions'])
    nai_story = {
    "storyContainerVersion": 1,
    "metadata": {
        "storyMetadataVersion": 1,
        "title": adventure['title'],
        "description": adventure['description'],
        "favorite": False,
        "tags": adventure['tags'],
        "isModified": True
    },
    "content": {
        "storyContentVersion": 5,
        "settings": {
        "parameters": {
        "textGenerationSettingsVersion": 3,
        "temperature": 0.63,
        "max_length": 40,
        "min_length": 1,
        "top_k": 0,
        "top_p": 0.975,
        "top_a": 1,
        "typical_p": 1,
        "tail_free_sampling": 0.975,
        "repetition_penalty": 2.975,
        "repetition_penalty_range": 2048,
        "repetition_penalty_slope": 0.09,
        "repetition_penalty_frequency": 0,
        "repetition_penalty_presence": 0,
        "order": [
          {
            "id": "top_p",
            "enabled": True
          },
          {
            "id": "top_k",
            "enabled": True
          },
          {
            "id": "tfs",
            "enabled": True
          },
          {
            "id": "temperature",
            "enabled": True
          },
          {
            "id": "top_a",
            "enabled": False
          },
          {
            "id": "typical_p",
            "enabled": False
          }
        ]
      },
        "model": "euterpe-v2"
        },
        "story": {
        "version": 2,
        "step": len(adventure['actions']),
        "datablocks": adventure['actions'],
        "currentBlock": len(adventure['actions'])+1,
        "fragments": adventure['actionfragments']
        },
        "context": [
        {
            "text": adventure['memory'],
            "contextConfig": {
            "prefix": "",
            "suffix": "\n",
            "tokenBudget": 2048,
            "reservedTokens": 0,
            "budgetPriority": 800,
            "trimDirection": "trimBottom",
            "insertionType": "newline",
            "maximumTrimType": "sentence",
            "insertionPosition": 0
            }
        },
        {
            "text": adventure['authorsnote'],
            "contextConfig": {
            "prefix": "",
            "suffix": "\n",
            "tokenBudget": 2048,
            "reservedTokens": 2048,
            "budgetPriority": -400,
            "trimDirection": "trimBottom",
            "insertionType": "newline",
            "maximumTrimType": "sentence",
            "insertionPosition": -4
            }
        }
        ],
        "lorebook": {
        "lorebookVersion": 4,
        "entries": adventure['worldinfo'],
        "settings": {
            "orderByKeyLocations": False
        },
        "categories": []
        },
        "storyContextConfig": {
        "prefix": "",
        "suffix": "",
        "tokenBudget": 2048,
        "reservedTokens": 512,
        "budgetPriority": 0,
        "trimDirection": "trimTop",
        "insertionType": "newline",
        "maximumTrimType": "sentence",
        "insertionPosition": -1,
        "allowInsertionInside": True
        },
        "ephemeralContext": [],
        "contextDefaults": {
        "ephemeralDefaults": [
            {
            "text": "",
            "contextConfig": {
                "prefix": "",
                "suffix": "\n",
                "tokenBudget": 2048,
                "reservedTokens": 2048,
                "budgetPriority": -10000,
                "trimDirection": "doNotTrim",
                "insertionType": "newline",
                "maximumTrimType": "newline",
                "insertionPosition": -2
            },
            "startingStep": 1,
            "delay": 0,
            "duration": 1,
            "repeat": False,
            "reverse": False
            }
        ],
        "loreDefaults": []
        },
        "settingsDirty": False,
        "didGenerate": True,
        "phraseBiasGroups": [
        {
            "phrases": [],
            "ensureSequenceFinish": False,
            "generateOnce": True,
            "bias": 0,
            "enabled": True,
            "whenInactive": False
        }
        ],
        "bannedSequenceGroups": [
        {
            "sequences": [],
            "enabled": True
        }]}}
    return nai_story

def create_blank_aid_scenario():
    resp = requests.post(url, '{"operationName":"ProfileContextCreateScenario","variables":{},"query":"mutation ProfileContextCreateScenario { createScenario { ...ScenarioEditScenario }}fragment ScenarioEditScenario on Scenario {publicId}"}', headers = headers)
    json_resp = resp.json()
    return json_resp['data']['createScenario']['publicId']

def add_aid_scenario_details(publicid, scenario):
    requests.post(url, f'{{"operationName":"ScenarioEditScreenUpdateScenario","variables":{{"input":{{"publicId":"{publicid}","title":{json.dumps(scenario["title"])},"description":{json.dumps(scenario["description"])},"prompt":{json.dumps(scenario["prompt"])},"memory":{json.dumps(scenario["memory"])},"authorsNote":{json.dumps(scenario["authorsnote"])},"tags":{json.dumps(scenario["tags"])},"nsfw":false,"featured":false,"safeMode":true,"thirdPerson":false,"allowComments":true}}}},"query":"mutation ScenarioEditScreenUpdateScenario($input: ScenarioInput) {{ updateScenario(input: $input) {{ ...ScenarioEditScenario }}}}fragment ScenarioEditScenario on Scenario {{ publicId description memory authorsNote prompt title }}"}}', headers = headers)

def add_world_info_to_aid(publicid, worldinfo):
    requests.post(url, f'{{"operationName":"WorldInfoManagerDisplayContextCreateActiveWorldInfo","variables":{{"worldInfoWithIds":[],"worldInfoWithNoIds":{json.dumps(worldinfo)},"contentPublicId":"{publicid}","contentType":"scenario"}},"query":"mutation WorldInfoManagerDisplayContextCreateActiveWorldInfo($worldInfoWithIds: JSONObject, $worldInfoWithNoIds: JSONObject, $contentPublicId: String, $contentType: String) {{ createWorldInfo(worldInfoWithIds: $worldInfoWithIds, worldInfoWithNoIds: $worldInfoWithNoIds, contentPublicId: $contentPublicId, contentType: $contentType) {{ id }}}}"}}', headers = headers)

def convert_wi_to_aid(worldinfo):
    aid_wi = []
    for x in range(len(worldinfo)):
        aid_wi.append({"name": worldinfo[x]['name'], "keys": ",".join(worldinfo[x]['keys']), "entry": worldinfo[x]['entry']})
    return aid_wi

# window layouts
load_layout = [[sg.Button("AID Scenario/Adventure", key = "-LOADAID-"), sg.Button("NAI .scenario", key = "-LOADNAI-")]]
details_layout = [[sg.Text("(No details to show)", key = "-DETAILS-")]]
export_layout = [[sg.Button("To AID Scenario", key = "-SAVEAID-", disabled = True), sg.Button("To NAI .scenario", key = "-SAVENAI-", disabled = True)]] # sg.Button("To NAI .story", key = "-SAVENAISTORY-") .story conversion doesn't work so this is out for now
left_layout = [
                [sg.Frame("Load scenario", load_layout, expand_x = True)],
                [sg.Frame("Scenario Details", details_layout, expand_x = True, expand_y = True)],
                [sg.Frame("Export scenario", export_layout, expand_x = True)]]
right_layout = [
                [sg.Text("Prompt")],
                [sg.Multiline(disabled = True, key = "-PROMPT-", expand_x = True, expand_y = True)],
                [sg.Text("Memory")],
                [sg.Multiline(disabled = True, key = "-MEMORY-", expand_x = True, expand_y = True)],
                [sg.Text("Author's Note")],
                [sg.Multiline(disabled = True, key = "-AUTHORSNOTE-", expand_x = True)]]
win_layout = [[sg.Column(left_layout, key = "-LEFT-", element_justification = "left", expand_x = True, expand_y = True), sg.Column(right_layout, key = "-RIGHT-", element_justification = "right", expand_x = True, expand_y = True)]]

def aid_window():
    fetch_aid_layout = [[sg.Text("Enter link to an AID scenario or adventure page. It should look like:\nhttps://play.aidungeon.io/main/scenarioView?publicId=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx\nhttps://play.aidungeon.io/main/adventureView?publicId=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx\nWARNING: You MUST own the content to load it. Not my ")],
                [sg.Input(key = "-LINK-", expand_x = True)],
                [sg.Button("Fetch"), sg.Button("Cancel")]]
    return sg.Window("Load AID scenario", fetch_aid_layout, modal = True)

def nai_window():
    browse_layout = [[sg.Text("Enter path to scenario file, or click browse.\nWARNING: Converting NovelAI scenarios to AI Dungeon will lose NovelAI-specific configurations.")],
                [sg.Input(key = "-FILEPATH-", expand_x = True), sg.FileBrowse()],
                [sg.Button("Open"), sg.Button("Cancel")]]
    return sg.Window("Load NAI scenario", browse_layout, modal = True)

# window functionality
def main_window():
    window = sg.Window("AID-CCT", win_layout, resizable = True, auto_size_buttons = True)
    while True:
        scenario_updated = False
        event, values = window.read()
        if event == sg.WINDOW_CLOSED: break
        elif event == "-LOADAID-":
            aid_win = aid_window()
            while True:
                event, values = aid_win.read()
                if event == sg.WINDOW_CLOSED or event == "Cancel": break
                # check out that link
                if "https://play.aidungeon.io/main/scenarioView?publicId=" in values["-LINK-"]:
                    # parse link, get publicId
                    publicid = values["-LINK-"].replace("https://play.aidungeon.io/main/scenarioView?publicId=", "")
                    if len(publicid) != 36:
                        sg.popup("Please enter a valid AID link. It should look like either:\nhttps://play.aidungeon.io/main/scenarioView?publicId=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx\nhttps://play.aidungeon.io/main/adventureView?publicId=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx", title = "Error parsing link")
                    else:
                        # request scenario
                        scenario = fetch_scenario(publicid)
                        if scenario is not None:
                            # nab WI from valid scenario
                            worldinfo = fetch_world_info(publicid, "scenario")
                            worldinfo = assemble_wi_from_aid(worldinfo)
                            loaded_scenario = assemble_from_aid_scenario(scenario, worldinfo)
                            scenario_updated = True
                            break
                        else:
                            sg.popup("The API returned an error attempting to fetch that content.\nEnsure that your link is valid and that the site isn't experiencing issues.", title = "Error fetching scenario")
                elif "https://play.aidungeon.io/main/adventureView?publicId=" in values["-LINK-"]:
                    # parse link, get publicId
                    publicid = values["-LINK-"].replace("https://play.aidungeon.io/main/adventureView?publicId=", "")
                    if len(publicid) != 36:
                        sg.popup("Please enter a valid AID link. It should look like either:\nhttps://play.aidungeon.io/main/scenarioView?publicId=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx\nhttps://play.aidungeon.io/main/adventureView?publicId=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx", title = "Error parsing link")
                    else:
                        # request adventure
                        adventure = fetch_adventure(publicid)
                        # because i have to fetch memory/AN in a seperate request...
                        adventure['memory'], adventure['authorsNote'] = fetch_adventure_extras(publicid)
                        if adventure is not None:
                            # nab WI from valid adventure
                            worldinfo = fetch_world_info(publicid, "adventure")
                            worldinfo = assemble_wi_from_aid(worldinfo)
                            loaded_scenario = assemble_from_aid_scenario(adventure, worldinfo)
                            scenario_updated = True
                            break
                        else:
                            sg.popup("The API returned an error attempting to fetch that content.\nEnsure that your link is valid and that the site isn't experiencing issues.", title = "Error fetching adventure")

                else:
                    sg.popup("Please enter a valid AID scenario or adventure link. It should look like either:\nhttps://play.aidungeon.io/main/scenarioView?publicId=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx\nhttps://play.aidungeon.io/main/adventureView?publicId=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx", title = "Error parsing link")
            aid_win.close()
        elif event == "-LOADNAI-":
            nai_win = nai_window()
            while True:
                event, values = nai_win.read()
                if event == sg.WINDOW_CLOSED or event == "Cancel": break
                elif event == "Open":
                    # check if it's a .scenario by checking the end of the filename
                    if values['-FILEPATH-'][-9:] != ".scenario":
                        sg.popup("Please select a valid .scenario file only.", title = "Error opening .scenario")
                    else:
                        scenario = fetch_nai_scenario(values['-FILEPATH-'])
                        worldinfo = assemble_wi_from_nai(scenario)
                        loaded_scenario = assemble_from_nai_scenario(scenario, worldinfo)
                        scenario_updated = True
                        break
            nai_win.close()
        elif event == "-SAVENAI-":
            # convert WI to NAI format, then pack it all into a .scenario
            loaded_scenario['worldinfo'] = convert_wi_to_nai(loaded_scenario['worldinfo'])
            scenario = assemble_nai_scenario(loaded_scenario)
            filename = export_converted_nai_scenario(scenario)
            sg.popup(f"Done!\nSaved under the filename {filename}.scenario", title = "Success")
        #elif event == "-SAVENAISTORY-":
            #loaded_scenario['worldinfo'] = convert_wi_to_nai(loaded_scenario['worldinfo'])
            #adventure = assemble_nai_story(loaded_scenario)
            #print(adventure)
            #filename = export_converted_nai_story(adventure)
            #sg.popup(f"Done!\nSaved under the filename {filename}.story", title = "Success")
        elif event == "-SAVEAID-":
            # make a blank AID scenario and upload scenario contents into it
            publicid = create_blank_aid_scenario()
            add_aid_scenario_details(publicid, loaded_scenario)
            # convert WI to AID format and upload it
            worldinfo = convert_wi_to_aid(loaded_scenario['worldinfo'])
            add_world_info_to_aid(publicid, worldinfo)
            sg.popup(f"Done!\nImported at https://play.aidungeon.io/main/scenarioView?publicId={publicid}", title = "Success")
        # if a new scenario is loaded, update details in window
        if scenario_updated:
            # update prompt/memory/author's note previews and details section
            if loaded_scenario['actions'] is not None:
                window['-DETAILS-'].update(f"Title: {loaded_scenario['title']}\nOrigin: {loaded_scenario['origin']}\nWorld info #: {len(loaded_scenario['worldinfo'])}\nPrompt tokens: {count_tokens(loaded_scenario['prompt'])}\nMemory tokens: {count_tokens(loaded_scenario['memory'])}\nAuthor's Note tokens: {count_tokens(loaded_scenario['authorsnote'])}\nAction #: {len(loaded_scenario['actions'])}\nTags: {display_tags(loaded_scenario['tags'])}")
            else:
                window['-DETAILS-'].update(f"Title: {loaded_scenario['title']}\nOrigin: {loaded_scenario['origin']}\nWorld info #: {len(loaded_scenario['worldinfo'])}\nPrompt tokens: {count_tokens(loaded_scenario['prompt'])}\nMemory tokens: {count_tokens(loaded_scenario['memory'])}\nAuthor's Note tokens: {count_tokens(loaded_scenario['authorsnote'])}\nTags: {display_tags(loaded_scenario['tags'])}")
            window['-PROMPT-'].update(loaded_scenario['prompt'])
            window['-SAVEAID-'].update(disabled = False)
            window['-SAVENAI-'].update(disabled = False)
            window['-MEMORY-'].update(loaded_scenario['memory'])
            window['-AUTHORSNOTE-'].update(loaded_scenario['authorsnote'])
            if loaded_scenario['origin'] == "AI Dungeon":
                window['-SAVEAID-'].update(disabled = True)
            if loaded_scenario['origin'] == "NovelAI":
                window['-SAVENAI-'].update(disabled = True)
            scenario_updated = False
    window.close()

def main():
    # get a firebase auth token before anything else
    fetch_firebase_token()
    main_window()

if __name__ == "__main__":
    main()
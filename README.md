# World of Tank Recruitment Bot
A Bot that monitors clans and notifies a specified Discord channel of members that have left for potential recruitment.
If a clan is disbanded then all members are considered potential recruits.

# Supplied Scripts
## get_clans.py
Retrieves all clan data and store it in a csv file. When supplied with a search string it will only return clans with the specified string inside their clan name.

**Note: retrieving all 200.000+ clans takes about 20 minutes**

```
options:
  -h, --help            show this help message and exit
  --log-level {critical,warning,error,info,debug}
                        Verbosity of logging
  --application-id ID   id of your Wargaming application
  --output-file FILE    File clan data will be stored in
  --search SEARCH       If supplied look for clan names with this string in the name. Else return all clans
```

## determine_language.py
Will loop over a file containing clan data and will try to determine the language used inside the description field.
It does this by using the FastText model. For more information on the underlying FastText model, refer to the official documentation: [FastText Language Identification.](https://fasttext.cc/docs/en/language-identification.html)
```
options:
options:
  -h, --help            show this help message and exit
  --log-level {critical,warning,error,info,debug}
                        Verbosity of logging
  --input-file INPUT_FILE, -i INPUT_FILE
                        File containing clan data
  --output-file OUTPUT_FILE, -o OUTPUT_FILE
                        File clan data will be stored in
  --language {af,als,am,an,ar,arz,as,ast,av,az,azb,ba,bar,bcl,be,bg,bh,bn,bo,bpy,br,bs,bxr,ca,cbk,ce,ceb,ckb,co,cs,cv,cy,da,de,diq,dsb,dty,dv,el,eml,en,eo,es,et,eu,fa,fi,fr,frr,fy,ga,gd,gl,gn,gom,gu,gv,he,hi,hif,hr,hsb,ht,hu,hy,ia,id,ie,ilo,io,is,it,ja,jbo,jv,ka,kk,km,kn,ko,krc,ku,kv,kw,ky,la,lb,lez,li,lmo,lo,lrc,lt,lv,mai,mg,mhr,min,mk,ml,mn,mr,mrj,ms,mt,mwl,my,myv,mzn,nah,nap,nds,ne,new,nl,nn,no,oc,or,os,pa,pam,pfl,pl,pms,pnb,ps,pt,qu,rm,ro,ru,rue,sa,sah,sc,scn,sco,sd,sh,si,sk,sl,so,sq,sr,su,sv,sw,ta,te,tg,th,tk,tl,tr,tt,tyv,ug,uk,ur,uz,vec,vep,vi,vls,vo,wa,war,wuu,xal,xmf,yi,yo,yue,zh}
                        Determine if the decsription is this language
  --threshold THRESHOLD
                        The average score has to be higher then this to be considered valid
```

## merge_lists.py
Combines multiple csv files containing clan data into a single file without any duplicates.
Files that are later in the list will overwrite earlier ones.

```
options:
  -h, --help            show this help message and exit
  -i INPUT_FILES [INPUT_FILES ...], --input-files INPUT_FILES [INPUT_FILES ...]
                        Files to be merged
  --output-file OUTPUT_FILE, -o OUTPUT_FILE
                        File clan data will be stored in
```

Example:
```sh
python merge_lists.py -i clanlist1.csv clanlist2.csv clanlist3.csv -o all_clans.csv

```
# Requirements
 - Docker
 - Docker Compose
 - Wargaming.net application ID
 - Discord Webhooks (one for logging, one for recruits)
 - Data file containing Clan Names that are to be monitored (csv file)

## Setup Docker
You can run the python script directly but it is recommended to use the supplied docker compose file.
The following setup assumes that you are running a debian/ubuntu based system/
To install Docker etc. perform the following steps:
### Install Prerequisites
```sh
sudo apt update
sudo apt install apt-transport-https ca-certificates curl gnupg lsb-release
```
### Add Docker’s Official GPG Key
```sh
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
```

### Add Docker Repo to Ubuntu
```sh
sudo echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" > /etc/apt/sources.list.d/docker.list 
sudo apt update
```

### Install Docker with plugins
```sh
sudo apt install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```
## Wargaming Application ID
In order to be allowed to talk to the wargaming API you will need to have an account with a phone number coupled to it.
Then you are allowed to create your own applications.

### creating Application
Login to https://developers.wargaming.net/ and go to `My Applications`.

Click `Add Application` and give it a fun name. You can choose between a server application or a mobile application. The server application needs to have White listed IP Addresses that can use the application id. If you do not want to bother with it choose the mobile application option.


Click on your newly created application and go to its settings (little gear top right).

Take a note of the ID, we will be needing it in a moment.

## Discord Webhooks
Discord has so called Webhooks. These are URL's which give you direct access to a channel. So treat it as a password. Because anybody can send data to it and then it will end up as a message inside the channel the webhook is affiliated with.


We will need 2 webhooks. One is used for general logging of the application. The other is used to specifically alert about potential recruits.
### Making a Webhook

1.  Open your **Server Settings** and head into the **Integrations** tab:
2.  Click the "**Create Webhook**" button to create a new webhook!

![Screen_Shot_2020-12-15_at_4.41.53_PM.png](https://support.discord.com/hc/article_attachments/1500000463501)

You'll have a few options here. You can:

-    **Edit the avatar:** By clicking the avatar next to the Name in the top left
-   **Choose what channel the Webhook posts to:** By selecting the desired text channel in the  dropdown menu.
-   **Name your Webhook:** Good for distinguishing multiple webhooks for multiple different services.

You now have your own handy URL.

![Screen_Shot_2020-12-15_at_4.51.38_PM.png](https://support.discord.com/hc/article_attachments/360101553853)

## Data file
We'll need a csv file containing the names of the clans that are to be monitored and their Clan ID's.
generate this file using get_clans.py
The file needs the following structure:
| name|clan_id|tag|is_clan_disbanded|old_name|members_cout|description|members|
| --- | --- |---|---|---|---|---|---|
| clan 1| 123  | || ||||
| clan 2 |456 | |||||

***generate this list using the supplied python scripts***


# Setup

Now that we have our application ID, webhooks and datafile ready we can setup the application.

First git clone this repo inside a directory.
```sh
mkdir ~/Wot_Bot
cd ~/Wot_Bot
git clone https://github.com/Klabost/WOT_recruitment_bot.git
```
Also copy the datafile containing the clan names to this directory
```sh
cp <datafile_location> ~/Wot_bot
```

You can configure the bot by using parameters on the commmand line or by setting environmental variables.
Command line has precedence over the environmental variables


| CLI parameter | ENV equivelant |Default value| Function|
|---|---|---|---|
|--log-level|LOG_LEVEL|INFO|Verbosity of the logging (options: critical, warning, error, info, debug)|
|--data-file| DATAFILE|| filename of csv file with clan names|
|--rate-limit|WOT_RATE_LIMIT|10| number of request per second to Wargaming API|
|--discord-logging-url|DISCORD_LOGGING_WEBHOOK| |Webhook to logging channel|
|--discord-recruit-url|DISCORD_RECRUITMENT_WEBHOOK|| Webhook to recruitment channel|
|--application-id|APPLICATION_ID||application id of your wargaming application|
|--update-interval|UPDATE_INTERVAL|60\*60| time in seconds between updating members list from clan|


You can change the log level but info will supply you with all the info that you will need for normal operations.

The Wargaming API is also rate limited between 10 request per second and 20. So this is set to the lower value. This doesn't need to be optimised.


# Running the App

When using the app with docker compose, put all the environmental variables inside a .env file.
Rename the supplied env.example to .env and set the values that you want to use.
If all the previous steps where taken then you only need to run.

Quick tip. The user inside the docker container is 999, so make sure it has writing permissions for the datafile.
```sh
docker compose up -d 
```


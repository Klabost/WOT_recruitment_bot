# World of Tank Recruitment Bot
A Bot that monitors clans and notifies a specified Discord channel of members that have left for potential recruitment.
If a clan is disbanded then all members are considered potential recruits.


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
We'll need a csv file containing the names of the clans that are to be monitored.

The file needs the following structure:
| name|clan_id|is_clan_disbanded|old_name|
| --- | --- |---|---|
| clan 1|| | |
| clan 2 | | |


The application needs to have at least the name specified. All other values will be added by the application if they are empty. This file will be edited by the application so keep a copy safe somewhere.

Easiest way to create this file is to create the table in excel or libre calc and then save it as a csv file.

You can also use the wot_example.csv file.

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
Now we will add the application ID and the webhooks to the config file.
First rename the `env.example` file to `.env`
Now edit this .env file and file out all empty lines.
```txt
LOG_LEVEL=info
APPLICATION_ID=                 <------------------
DATAFILE=                       <------------------
WOT_RATE_LIMIT=10
DISCORD_LOGGING_WEBHOOK=        <------------------
DISCORD_RECRUITMENT_WEBHOOK=    <------------------
```

You can change the log level but info will supply you with all the info that you will need for normal operations.

The Wargaming API is also rate limited between 10 request per second and 20. So this is set to the lower value. This doesn't need to be optimised.

The docker compose file will use this .env file to supply the python application running inside a docker container with all the information it needs.

# Running the App

If all the previous steps where taken then you only need to run.

Small tip. The user inside the docker container is 999, so make sure it has writing permissions for the datafile.
```sh
docker compose up -d 
```


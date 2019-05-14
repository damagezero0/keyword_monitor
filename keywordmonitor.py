#! /usr/bin/env python
#coding: utf-8

import os
import sys
import requests
import smtplib
import time
import json
import traceback
import ConfigParser
from datetime import datetime
from email.mime.text import MIMEText


def logging(message, is_keyword):
    
    # standard output
    print("[INFO] {0}".format(message))
    result = json.dumps(message)

    if is_keyword:
        with  open(logfile_keyword, 'a') as f:
            f.write("[{0}] [INFO] {1}\n".format(get_time(), result))
    else:
        with  open(logfile_monitor, 'a') as f:
            f.write("[{0}] [INFO] {1}\n".format(get_time(), message))


def get_time():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def config_load():

    configfile = "./etc/config.ini"
    
    if not os.path.exists(configfile):
        print("[ERROR]{0} dose not exist".format(configfile))
        sys.exit(1)

    with open(configfile, 'r') as f:

        ini = ConfigParser.ConfigParser()
        ini.read('./etc/config.ini')

        global max_sleep_time
        max_sleep_time = float(ini.get('DEFAULT','max_sleep_time'))

        global alert_email_from
        alert_email_from = ini.get('DEFAULT','alert_email_from')

        global alert_email_password
        alert_email_password = ini.get('DEFAULT','alert_email_password')

        global alert_email_to
        alert_email_to = ini.get('DEFAULT','alert_email_to')

        global logfile_monitor
        logfile_monitor = os.path.join(ini.get('DEFAULT','logpath'), ini.get('DEFAULT','logfilename_monitor'))

        global logfile_keyword 
        logfile_keyword = os.path.join(ini.get('DEFAULT','logpath'), ini.get('DEFAULT','logfilename_keyword'))

        # read in our list of keywords
        global keywords
        with open("./etc/keywords.txt","r") as fd:
            file_contents = fd.read()
            keywords      = file_contents.splitlines()
            
        # load up our list of stored paste ID's and only check the new ones
        global pastebin_ids 
        if os.path.exists("./etc/pastebin_ids.txt"):
            with open("./etc/pastebin_ids.txt","rb") as fd:
                pastebin_ids = fd.read().splitlines()
        else:
            pastebin_ids = []

# Send email to you!
def send_alert(alert_email):
    
    email_body = "The following are keyword hits that were just found:\r\n\r\n"
    
    # walk through pastebin results
    if alert_email.has_key("pastebin"):
        
        for paste_id in alert_email['pastebin']:

            email_body += "\r\nPastebin Link: https://pastebin.com/%s\r\n" % paste_id
            email_body += "Keywords:%s\r\n" % ",".join(alert_email['pastebin'][paste_id][0])
            email_body += "Paste Body:\r\n%s\r\n\r\n" % alert_email['pastebin'][paste_id][1]
           
    # build the email message
    msg = MIMEText(email_body)
    msg['Subject'] = "Automating OSINT Keyword Alert"
    msg['From']    = alert_email_from
    msg['To']      = alert_email_to
    
    server = smtplib.SMTP("smtp.gmail.com",587)
    
    server.ehlo()
    server.starttls()
    server.login(alert_email_account,alert_email_password)
    server.sendmail(alert_email_account,alert_email_account,msg.as_string())
    server.quit()
    
    logging("Alert email sent!", False)

    return


# Check Pastebin for keyword list.
def check_pastebin(keywords):
    
    new_ids    = []
    paste_hits = {}
    
    # poll the Pastebin API
    try:
        response = requests.get("https://scrape.pastebin.com/api_scraping.php?limit=250")
        
        if ("DOES NOT HAVE ACCESS")  in (str)(response.content) :
            logging(response.content, False)
            exit (-1)

    except:
        return paste_hits
    
    # parse the JSON
    result   = response.json()
        
    for paste in result:
    
        if paste['key'] not in pastebin_ids:
            
            new_ids.append(paste['key'])
    
            # this is a new paste so send a secondary request to retrieve
            # it and then check it for our keywords 
            paste_response       = requests.get(paste['scrape_url'])
            paste_body_lower     = paste_response.content.lower()
            paste_body_strings = str(paste_response.content).lstrip()
            
            keyword_hits = {}
            
            for keyword in keywords:
                
                if keyword.lower() in paste_body_lower:
                    #keyword_hits.update(keyword)
                    #keyword_hits.append(keyword)
                    keyword_hits[paste['key']] = keyword
                
            if len(keyword_hits):      
                paste_hits.update({"pastebin_id":"{0}".format(paste['key']), "keyword":"{0}".format(keyword),\
                        "row_data":"{0}".format(paste_body_strings)})
            
                logging("Hit on Pastebin(https://pastebin.com/) for {0}".format(keyword_hits), False)

    # store the newly checked IDs 
    with open("./etc/pastebin_ids.txt","ab") as fd:
        for pastebin_id in new_ids:
            fd.write("%s\r\n" % pastebin_id)
    
    logging("Successfully processed {0} Pastebin posts.".format(len(new_ids)), False)

    return paste_hits


def check_keywords(keywords):
    
    alert_email          = {}
    time_start = time.time()
    
    # now we check Pastebin for new pastes
    result = check_pastebin(keywords)
    
    if len(result.keys()):
        # we have results so include it in the alert email
        alert_email['pastebin'] = result
        
    time_end   = time.time()
    total_time = time_end - time_start
    
    # if we complete the above inside of the max_sleep_time setting
    # we sleep. This is for Pastebin rate limiting
    if total_time < max_sleep_time:
        sleep_time = max_sleep_time - total_time
        
        logging("Sleeping for {0} s".format(int(sleep_time)), False)
        time.sleep(sleep_time)
    
    return alert_email


if __name__ == "__main__":

    try:
        config_load()

    except Exception:
        print(traceback.format_exc())
        sys.exit(1)

    # execute your search once first to populate results
    check_keywords(keywords)

    # now perform the main loop
    while True:
        
        alert_email = check_keywords(keywords)
        
        if len(alert_email.keys()):
            #if we have alerts send them out
            logging(alert_email, True)
            #send_alert(alert_email)

#! /usr/bin/env python
#coding: utf-8

import os
import requests
import smtplib
import time
from datetime import datetime
from email.mime.text import MIMEText

max_sleep_time       = 60
alert_email_from  = "ACCOUNTS"
alert_email_password = "PASSWORD" 
alert_email_to  = "ACCOUNTS"
logfile="./log/keywordmonitor.log"


def logging(message):
    print("[INFO] {0}".format(message))
    with  open(logfile, 'a') as f:
        f.write("[{0}] [INFO] {1}\n".format(get_time(), message))


def get_time():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


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
    
    logging("Alert email sent!")

    return


# Check if the URL is new.
def check_urls(keyword,urls):
    
    new_urls = []
    
    if os.path.exists("keywords/%s.txt" % keyword):
        
        with open("keywords/%s.txt" % keyword,"r") as fd:
            stored_urls = fd.read().splitlines()
        
        for url in urls:
            if url not in stored_urls:
                
                logging("New URL for {0} discovered: {1}".format(keyword,url))
                new_urls.append(url)
                
    else:
        new_urls = urls
        
    # now store the new urls back in the file
    with open("keywords/%s.txt" % keyword,"ab") as fd:
        for url in new_urls:
            fd.write("%s\r\n" % url)
            
    return new_urls


# Check Pastebin for keyword list.
def check_pastebin(keywords):
    
    new_ids    = []
    paste_hits = {}
    
    # poll the Pastebin API
    try:
        response = requests.get("https://scrape.pastebin.com/api_scraping.php?limit=100")
        
        if ("DOES NOT HAVE ACCESS")  in (str)(response.content) :
            logging(response.content)
            exit (-1)

    except:
        return paste_hits
    
    # parse the JSON
    result   = response.json()
    
    # load up our list of stored paste ID's and only check the new ones
    if os.path.exists("pastebin_ids.txt"):
        with open("pastebin_ids.txt","rb") as fd:
            pastebin_ids = fd.read().splitlines()
    else:
        pastebin_ids = []
        
    for paste in result:
    
        if paste['key'] not in pastebin_ids:
            
            new_ids.append(paste['key'])
    
            # this is a new paste so send a secondary request to retrieve
            # it and then check it for our keywords 
            paste_response       = requests.get(paste['scrape_url'])
            paste_body_lower     = paste_response.content.lower()
            
            keyword_hits = []
            
            for keyword in keywords:
                
                if keyword.lower() in paste_body_lower:
                    keyword_hits.append(keyword)
                
            if len(keyword_hits):      
                paste_hits[paste['key']] = (keyword_hits,paste_response.content)
            
                logging("Hit on Pastebin for {0}: {1}".format(str(keyword_hits), paste['full_url']))

    # store the newly checked IDs 
    with open("pastebin_ids.txt","ab") as fd:
        for pastebin_id in new_ids:
            fd.write("%s\r\n" % pastebin_id)
    
    logging("Successfully processed {0} Pastebin posts.".format(len(new_ids)))

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
        
        logging("Sleeping for {0} s".format(int(sleep_time)))
        
        time.sleep(sleep_time)
    
    return alert_email


if __name__ == "__main__":

    if not os.path.exists("keywords"):
        os.mkdir("keywords")

    # read in our list of keywords
    with open("./keywords/keywords.txt","r") as fd:
        file_contents = fd.read()
        keywords      = file_contents.splitlines()

    # execute your search once first to populate results
    check_keywords(keywords)

    # now perform the main loop
    while True:
        
        alert_email = check_keywords(keywords)
        
        if len(alert_email.keys()):
            #if we have alerts send them out
            logging(alert_email)
            #send_alert(alert_email)

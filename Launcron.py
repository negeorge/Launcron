# references: http://www.twilio.com/docs/quickstart/python/sms/replying-to-sms-messages

import flask
import twilio.twiml
import pymongo
import time
import twilio.rest
import os
import logging, sys
import urlparse

# Flask does not by default show logs in production: 
# http://stackoverflow.com/questions/8007176/500-error-without-anything-in-the-apache-logs
logging.basicConfig(stream=sys.stderr)

# create an instance of the Twilio REST client
# add your own Twilio account_sid, auth_token and notification_number
account_sid = {}
auth_token = {}
client = twilio.rest.TwilioRestClient(account_sid, auth_token)
notification_number = {}
 
# create a instance of a Flask application called laundryapp 
laundryapp = flask.Flask(__name__)

# https://gist.github.com/2032410
# Heroku uses MongoHQ to create a mongodb, provides a MONGO_URL w/ host, port, u/n, p/w, db name
MONGO_URL = os.environ.get('MONGOHQ_URL')

# if trying to connect to a mongodb on Heroku
if MONGO_URL:
    # Get a connection to the Heroku MongoHQ MONGO_URL
    conn = pymongo.Connection(MONGO_URL)
    
    # Heroku specifies a database in the path of the URL, get this database
    db = conn[urlparse.urlparse(MONGO_URL).path[1:]]

#if not trying to connect to a mongodb on Heroku, connect to mongodb on localhost
else:
    conn = pymongo.Connection('localhost', 27017)
    db = conn['laundry_database']


# Notify anyone on the waitlist that the washers are now free
def notify_waitlist(waitlist):
    for x in waitlist:
        # convert the current washer user's phone number to a string
        tonumber = str(x)
        # use the Twilio REST API to send a message to anyone on the waitlist
        # **** comment this out when testing, otherwise lots of text message charges! ****
        outbound_message = client.sms.messages.create(to=tonumber, from_=notification_number, body="Run quick! The washer is now free!")
        
        # *** for use in testing ***
        # print out a log message to show who was notified
        print "Messages sent to %s" % (tonumber)


# Respond to incoming messages with laundry status updates
@laundryapp.route("/", methods=['GET', 'POST'])
def laundry():
    # fetch washer document if it exists
    # if no washer document, create a template
    washer = db.machines.find_one({'machine':'washer'})
    if washer == None:
        washer = db.machines.save({'machine':'washer','user':0,'starttime':0, 'waitlist':[], 'sentmessage':False})

    # grab user phone number and code from SMS message
    from_number = flask.request.values.get('From', None)
    # grab the incoming code and convert to upper case
    action = flask.request.values.get('Body', 'no command').upper()
    # create a Twilio Response object 
    resp = twilio.twiml.Response()
    
    if action == "BW":
        # generate current time in seconds 
        timestamp = int(time.time())
         # look up the value of the user key in the washer document 
        if washer['user'] == 0:
            # update database with user phone no & timestamp
            db.machines.update(washer, {'$set':{'user':from_number, 'starttime':timestamp}})
            # attach an sms TwiML verb to our response object with a sms message body
            resp.sms("We'll let you know when your washer load is done")
        else:
            resp.sms("ERROR: Washer already marked as busy")
    
    elif action == "AW":
        # check if person who messaged in AW is the same person who started the washer
        if from_number == washer['user']:
            resp.sms("Thanks for letting us know your washer is now available")
            # notify everyone on waitlist washer is free by calling the notify_waitlist function
            notify_waitlist(washer['waitlist'])
            # update database to clear user phone no & timestamp
            db.machines.update(washer, {'$set':{'user':0, 'starttime':0, 'sentmessage':False, 'waitlist':[]}})
        else: 
            # if the person who messaged in does not own the washer, send error message
            resp.sms("ERROR: Your laundry is not currently in this washer")
        

    elif action == "CW":
        # look up the value of the user key in the washer document 
        if washer['user'] == 0:
            resp.sms("Hurray! A washer is now available!")
        else:
            resp.sms("Sorry, all washers are busy. We'll update you when one is available")
            # add user number to database waitlist
            db.machines.update(washer, {'$push':{'waitlist':from_number}})
    
    else:
        resp.sms("Sorry, I didn't understand. Please enter a valid code")
    
    # takes the response object and converts it into an xml format so Twilio 
    # can understand what to do
    return flask.Response(resp.toxml(), mimetype='text/xml')

# Requested by a cron job every minute
# Checks if the washer start time + 30 minutes and notifies
# person using the washer
@laundryapp.route("/update", methods=['GET', 'POST'])
def update():
    washer = db.machines.find_one({'machine':'washer'})
    # if there is no database yet or no active users, no need to go continue through the function
    if washer == None or washer['user'] == 0:
        return "No users set"
    # generate current time in seconds 
    timestamp = int(time.time())
    # create variable for when laundry cycle should be done (30 min = 30*60 CHANGE AFTER DEMO!!!!!)
    endlaundrytime = washer['starttime'] + 2*60 

    # if there is an active user,
    # check if the endlaundrytime has passed and if no reminder messages have been sent previously
    if timestamp >= endlaundrytime and washer['sentmessage'] == False:
        # convert the current washer user's phone number to a string
        tonumber = str(washer['user'])
        # use the Twilio REST API to send a message to the user to let them know their washer load is done
        outbound_message = client.sms.messages.create(to=tonumber, from_=notification_number, body="Your Laundry is done!")
        # to prevent sending multiple messages to user, tell the database we've already sent a message
        db.machines.update(washer, {'$set':{'sentmessage':True}})
        return "sending text message"
    # if no new message needs to be sent, sends a log message to show the last endlaundrytime  
    return "no updates needed at time %s endlaundrytime is %s" % (timestamp, endlaundrytime)
    
if __name__ == '__main__':
    print("Hello from LaundryApp")
    # Bind to PORT if defined, otherwise default to 5000.
    port = int(os.environ.get('PORT', 5000))
    laundryapp.run(host='0.0.0.0', port=port)

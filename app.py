# committing from virtual machine nano file
import os
import json
import logging
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from slackeventsapi import SlackEventAdapter
from flask import Flask, request, Response

# Initialize logging
logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__)

# Initialize Slack client and event adapter
slack_token = os.getenv("SLACK_BOT_TOKEN")
client = WebClient(token=slack_token)
slack_signing_secret = os.getenv("SLACK_SIGNING_SECRET")
slack_events_adapter = SlackEventAdapter(slack_signing_secret, "/slack/events", app)

# Route for Slack event subscriptions
@app.route('/slack/events', methods=['POST'])
def slack_events():
    if request.json.get('type') == 'url_verification':
        return Response(request.json.get('challenge'), mimetype='text/plain')

    if 'payload' in request.form:
        payload = json.loads(request.form['payload'])
        logging.debug('Payload: %s', payload)
        if payload['type'] == 'view_submission':
            handle_view_submission(payload)
    return Response(), 200

def handle_view_submission(payload):
    view_data = payload['view']['state']['values']
    title = view_data['title_block']['title']['value']
    location = view_data['location_block']['location']['value']
    date = view_data['datetime_block']['date']['selected_date']
    time = view_data['time_block']['time']['selected_time']
    timezone = view_data['timezone_block']['timezone']['value']
    user_id = payload['user']['id']
    channel_id = payload['view']['private_metadata']

    # Combine date and time, then convert to UTC
    datetime_str = f"{date} {time}"
    local_tz = pytz.timezone(timezone)
    local_dt = local_tz.localize(datetime.strptime(datetime_str, "%Y-%m-%d %H:%M"))
    utc_dt = local_dt.astimezone(pytz.utc)

    # Format the UTC time for the link
    formatted_time = utc_dt.strftime("%Y%m%dT%H%M%S")
    link = f"https://time.cs50.io/{formatted_time}+0000/PT1H?title={title}&location={location}"

    # Send the link back to the user
    client.chat_postMessage(channel=user_id, text=f"Here is your event link: {link}")

# Listen for messages containing "create event"
@slack_events_adapter.on("message")
def handle_message(event_data):
    message = event_data["event"]
    logging.debug('Message: %s', message)

    text = message.get('text')
    channel_id = message.get('channel')
    user = message.get('user')

    if "create event" in text.lower():
        try:
            # Open a modal with input fields
            client.views_open(
                trigger_id=message.get("trigger_id"),  # Use trigger_id to open the modal
                view={
                    "type": "modal",
                    "callback_id": "event_creation",
                    "title": {"type": "plain_text", "text": "Create Event"},
                    "blocks": [
                        {
                            "type": "input",
                            "block_id": "title_block",
                            "element": {
                                "type": "plain_text_input",
                                "action_id": "title",
                                "placeholder": {"type": "plain_text", "text": "Event Title"}
                            },
                            "label": {"type": "plain_text", "text": "Title"}
                        },
                        {
                            "type": "input",
                            "block_id": "location_block",
                            "element": {
                                "type": "plain_text_input",
                                "action_id": "location",
                                "placeholder": {"type": "plain_text", "text": "Event Location"}
                            },
                            "label": {"type": "plain_text", "text": "Location"}
                        },
                        {
                            "type": "input",
                            "block_id": "datetime_block",
                            "element": {
                                "type": "datepicker",
                                "action_id": "date",
                                "placeholder": {"type": "plain_text", "text": "Select a date"}
                            },
                            "label": {"type": "plain_text", "text": "Date"}
                        },
                        {
                            "type": "input",
                            "block_id": "time_block",
                            "element": {
                                "type": "timepicker",
                                "action_id": "time",
                                "placeholder": {"type": "plain_text", "text": "Select a time"}
                            },
                            "label": {"type": "plain_text", "text": "Time"}
                        },
                        {
                            "type": "input",
                            "block_id": "timezone_block",
                            "element": {
                                "type": "plain_text_input",
                                "action_id": "timezone",
                                "placeholder": {"type": "plain_text", "text": "e.g., America/New_York"}
                            },
                            "label": {"type": "plain_text", "text": "Timezone"}
                        }
                    ],
                    "submit": {"type": "plain_text", "text": "Create"}
                }
            )
        except SlackApiError as e:
            client.chat_postMessage(
                channel=channel_id, 
                text=f"Error opening modal: {e.response['error']}. My human might be able to help: <@LKMW>"
            )

if __name__ == "__main__":
    app.run(port=3000)

import boto3, json, os, logging, datetime, time

pinpoint_client = boto3.client('pinpoint')
ddb = boto3.client('dynamodb')
table_name = os.environ['TABLE_NAME']
# This function can be used within an Amazon Pinpoint Campaign or Amazon Pinpoint Journey.

def lambda_handler(event, context):

    logging.getLogger().setLevel('INFO')
    # print the payload the Lambda was invoked with
    logging.info(event)
    logging.info(table_name)

    if 'Endpoints' not in event:
        return "Function invoked without endpoints."
    # A valid invocation of this channel by the Pinpoint Service will include Endpoints in the event payload

    campaign_id = event['CampaignId']
    application_id = event['ApplicationId']

    custom_events_batch = {}
    # Gather events to emit back to Pinpoint for reporting

    for endpoint_id in event['Endpoints']:
        endpoint_profile = event['Endpoints'][endpoint_id]
        # the endpoint profile contains the entire endpoint definition.
        # Attributes and UserAttributes can be interpolated into your message for personalization.

        surface = "Website_HomePage"
        # surface allows you to map many messages to the same EndpointID
        # e.g. message for the Website Home Page, or a message for the Welcome Screen

        message = "Welcome to the Home Page! Here is your offer!"
        # construct your message here.  You have access to the endpoint profile to personalize the message with Attributes.
        # e.g. message = "Hello {name}!  -Pinpoint Voice Channel".format(name=endpoint_profile["Attributes"]["FirstName"])

        ttl = int(time.time()) + (7 * 24 * 60 * 60)
        # how long should the message live for
        # e.g. offer only valid for 7 days


        rowitem = {
            'EndpointId': {
                'S': endpoint_id
            },
            'Surface': {
                'S': surface
            },
            'Message': {
                'S': message
            },
            'ttl': {
                'N': "%s" % (ttl)
            }
        }

        try:
            response = ddb.put_item( TableName=table_name,
                ReturnConsumedCapacity='TOTAL',
                Item=rowitem
            )
            logging.info(response)

            custom_events_batch[endpoint_id] = create_success_custom_event(endpoint_id, campaign_id, surface, message, ttl)

        except Exception as e:
            logging.error(e)
            logging.error("Error trying to write the message to dynamodb")
            custom_events_batch[endpoint_id] = create_failure_custom_event(endpoint_id, campaign_id, e)

    try:
        # submit events back to Pinpoint for reporting
        put_events_result = pinpoint_client.put_events(
            ApplicationId=application_id,
            EventsRequest={
                'BatchItem': custom_events_batch
            }
        )
        logging.info(put_events_result)
    except Exception as e:
        logging.error(e)
        logging.error("Error trying to send custom events to Pinpoint")


    logging.info("Complete")
    return "Complete"

def create_success_custom_event(endpoint_id, campaign_id, surface, message, ttl):
    custom_event = {
        'Endpoint': {},
        'Events': {}
    }
    custom_event['Events']['dynamodb_%s_%s' % (endpoint_id, campaign_id)] = {
        'EventType': 'dynamodb.success',
        'Timestamp': datetime.datetime.now().isoformat(),
        'Attributes': {
            'campaign_id': campaign_id,
            'surface': surface,
            'message': (message[:195] + '...') if len(message) > 195 else message,
            'ttl': "%s" % (ttl)
        }
    }
    return custom_event

def create_failure_custom_event(endpoint_id, campaign_id, e):
    error = repr(e)
    custom_event = {
        'Endpoint': {},
        'Events': {}
    }
    custom_event['Events']['dynamodb_%s_%s' % (endpoint_id, campaign_id)] = {
        'EventType': 'dynamodb.failure',
        'Timestamp': datetime.datetime.now().isoformat(),
        'Attributes': {
            'campaign_id': campaign_id,
            'error': (error[:195] + '...') if len(error) > 195 else error
        }
    }
    return custom_event

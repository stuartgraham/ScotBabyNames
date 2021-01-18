import boto3
import simplejson as json
import pprint
import os
import jinja2
from time import time
from operator import itemgetter
from boto3.dynamodb.conditions import Key, Attr
import random
import string
import uuid
import collections

# Boto3 Objects
dynamo_db_names_table = os.environ['DYNAMO_DB_NAMES']
dynamodb = boto3.resource('dynamodb')
table_names = dynamodb.Table(dynamo_db_names_table)


def get_name_data(name, gender):
    print(f'Name: {name}, Gender: {gender}')
    # Catch any gender case
    genders = ['B', 'G']
    if gender in genders:
        genders = [gender]

    items = collections.defaultdict(dict)

    # Random selection

    if name == 'Random':
        # This removes low count names by looking for 2019 stats
        counted_min = 2
        counted_use = 0
        while counted_use < counted_min:
            random_index = uuid.uuid4().hex
            random_gender = random.choice(genders)
            response = table_names.query(
                IndexName='bn_uuid_sort',
                Limit=1, 
                KeyConditionExpression=Key('uuid').gt(random_index[0:8]) & Key('gender').eq(str(random_gender))
            )
            item = response['Items'][0]
            try:
                counted_use = item['2019']['counted']
            except Exception as e:
                print(e)
                pass
        
        # Skims off DDB decimial type
        item = json.dumps(item)
        item = json.loads(item)
        print(item)
        items['name_data'][item['gender']] = item

    else:
    # Queried selection
        for i in genders:
            response = table_names.get_item(
                Key={
                    'name' :  name,
                    'gender' : i
                }
            )
            if 'Item' in response.keys():
                item = response['Item']
                # Skims off DDB decimial type
                item = json.dumps(item)
                item = json.loads(item)
                print(item)
                items['name_data'][item['gender']] = item

    if len(items) > 0:          
        items = json.dumps(items)
        items = json.loads(items)
        return items
    else:
        return {'status' : 'norecords'}


# Generate HTML for response
def gen_html(page_data):
    file_loader = jinja2.FileSystemLoader('templates')
    env = jinja2.Environment(loader=file_loader)
    template = env.get_template(page_data['page'] + '.html')
    output = template.render(page_data=page_data)
    return output


def handler(event, context):
    path_params = event['pathParameters']
    # Handle favicon.ico requests
    # if path_params['name'] == 'favicon.ico':
    #     favicon_url = 'https://stugraha-world-dev.s3-eu-west-1.amazonaws.com/lothianbus/favicon.ico'
    #     return {'body': '', 'headers': {'Location': favicon_url}, 'status_code': '301'}

    print(path_params)
    if 'name' in path_params.keys():
        name_data = get_name_data(path_params['name'].capitalize() , path_params['gender'].capitalize())
        print(name_data)
        name_data.update({'page' : 'name_detail'})
        html = gen_html(name_data)
    elif path_params['proxy'] == '':
        html = gen_html({'status' : 'norecords', 'page' : 'home'})
    else:
        html = gen_html({'status' : 'norecords', 'page' : '404'})

    return {
        'headers': {
            'Content-Type': 'text/html',
        },
        'body': html,
        'statusCode': '200'
    }


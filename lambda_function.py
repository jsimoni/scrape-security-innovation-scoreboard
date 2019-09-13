import requests
from datetime import datetime
#https://www.crummy.com/software/BeautifulSoup/bs4/doc/#installing-beautiful-soup
from bs4 import BeautifulSoup
#https://pandas.pydata.org/pandas-docs/stable/install.html
import pandas as pd
from github import Github
import boto3
import base64
import json

def lambda_handler(event, context):

	password = get_secret('cmd-ctrl-password')

	login_url='https://play.cmdnctrl.net/doLogin.action'
	payload = {
		"email": "jsimoni@ipipeline.com",
		"password": password
	}

	session_requests = requests.session()

	result = session_requests.post(
		login_url,
		data = payload,
		headers = dict(referer=login_url)
	)

	scoreboard_url = "https://play.cmdnctrl.net/Admin/viewAllReportCards?eventId=" + event['eventId']
	scoreboard_result = session_requests.get(
		scoreboard_url
	)

	soup = BeautifulSoup(scoreboard_result.text, 'lxml')
	table = soup.find('table',{'class':'table table-main table-bordered table-no-top-border'})

	n_columns = 0
	n_rows=0
	column_names = []

	# Find number of rows and columns
	# we also find the column titles if we can
	for row in table.find_all('tr'):

	    # Determine the number of rows in the table
	    td_tags = row.find_all('td')
	    if len(td_tags) > 0:
	        n_rows+=1
	        if n_columns == 0:
	            # Set the number of columns for our table
	            n_columns = len(td_tags)

	    # Handle column names if we find them
	    th_tags = row.find_all('th')
	    if len(th_tags) > 0 and len(column_names) == 0:
	        for th in th_tags:
	            column_names.append(th.get_text())

	# Safeguard on Column Titles
	if len(column_names) > 0 and len(column_names) != n_columns:
	    raise Exception("Column titles do not match the number of columns")

	columns = column_names if len(column_names) > 0 else range(0,n_columns)
	df = pd.DataFrame(columns = columns,
	                  index= range(0,n_rows))

	row_marker = 0
	for row in table.find_all('tr'):
	    column_marker = 0
	    columns = row.find_all('td')
	    for column in columns:
	        df.iat[row_marker,column_marker] = column.get_text()
	        column_marker += 1
	    if len(columns) > 0:
	        row_marker += 1

	# Convert to float if possible
	for col in df:
	    try:
	        df[col] = df[col].astype(float)
	    except ValueError:
	        pass


	df.insert(3, 'TEAM', df['PLAYER HANDLE'].str.slice(0, -3))
	current_time = datetime.utcnow()
	df.insert(4, 'DATETIME', current_time)
	groupby_team = df.groupby(['TEAM','DATETIME'], as_index=False)['SCORE'].mean()

	#groupby_team.to_json('current_score.json', orient='split')
	json_string = groupby_team.to_json(orient='split')

	api_key = get_secret('github-api-key')
	g = Github(api_key)

	repo = g.get_repo("jsimoni/jsimoni.github.io")
	contents = repo.get_contents("current_score.json")
	repo.update_file(contents.path, str(current_time), json_string, contents.sha, branch="master")

def get_secret(secret_key):
	secret_name = "hackerthon"
	region_name = "us-east-1"

	# Create a Secrets Manager client
	session = boto3.session.Session()
	client = session.client(
	    service_name='secretsmanager',
	    region_name=region_name
	)

	get_secret_value_response = client.get_secret_value(SecretId=secret_name)
	secret_string = get_secret_value_response['SecretString']
	secret_json = json.loads(secret_string)
	secret = secret_json.get(secret_key)

	return secret

if __name__ == '__main__':
	event = {'eventId': '81880'}
	lambda_handler(event, {})

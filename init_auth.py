# Notebook: 01_Init_Auth
import boto3

# 1. Get Long-Term Keys (Stored manually once)
# You only do the 'databricks secrets put' CLI command ONCE for these


ACCESS_KEY = dbutils.secrets.get(scope = "ticker", key = "access_key")
SECRET_KEY = dbutils.secrets.get(scope = "ticker", key = "secret_key")
SESSION_TOKEN = dbutils.secrets.get(scope = "ticker", key = "session_key")



# 3. Share these with downstream tasks using Task Values
# This is safe and scoped ONLY to this specific job run
dbutils.jobs.taskValues.set(key="temp_ak", value=ACCESS_KEY)
dbutils.jobs.taskValues.set(key="temp_sk", value=SECRET_KEY)
dbutils.jobs.taskValues.set(key="temp_token", value=SESSION_TOKEN)

print("Temporary credentials generated and passed to downstream tasks.")
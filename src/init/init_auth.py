# Notebook: src/init/init_auth
# Description: Centralizes AWS Authentication and broadcasts keys to downstream tasks.

# 1. Define Widgets for Manual Overrides (Useful for AWS Educate rotating keys)
dbutils.widgets.text("aws_access_key", "", "AWS Access Key")
dbutils.widgets.text("aws_secret_key", "", "AWS Secret Key")
dbutils.widgets.text("aws_session_token", "", "AWS Session Token")

# 2. Function to resolve credentials (Widget > Secret)
def get_credential(widget_name, secret_key):
    # Priority A: Check Widget (Manual Run)
    val = dbutils.widgets.get(widget_name)
    if val and val.strip():
        print(f"Using manual override for {secret_key}")
        return val.strip()
    
    # Priority B: Check Databricks Secrets (Scheduled Run)
    try:
        return dbutils.secrets.get(scope="ticker", key=secret_key)
    except Exception as e:
        print(f"Warning: Could not retrieve secret {secret_key}: {e}")
        return None

# 3. Retrieve Keys
access_key = get_credential("aws_access_key", "access_key")
secret_key = get_credential("aws_secret_key", "secret_key")
session_token = get_credential("aws_session_token", "session_key")

if not access_key or not secret_key:
    raise ValueError("CRITICAL: No AWS Credentials found in Widgets or Secrets.")

# 4. Broadcast to Downstream Tasks (Bronze, Silver, Gold)
# This allows downstream tasks to use: 
# dbutils.jobs.taskValues.get(taskKey="Init_Auth", key="temp_ak")
print("Broadcasting credentials to Task Values...")

dbutils.jobs.taskValues.set(key="temp_ak", value=access_key)
dbutils.jobs.taskValues.set(key="temp_sk", value=secret_key)
dbutils.jobs.taskValues.set(key="temp_token", value=session_token)

print("SUCCESS: Credentials initialized for this session.")
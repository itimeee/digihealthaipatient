# Google Cloud Platform Setup Guide
# คู่มือการตั้งค่า Google Cloud Platform

This guide will help you set up Google Cloud Platform (GCP) for the DigiHealth AI Patient application.
คู่มือนี้จะช่วยคุณตั้งค่า Google Cloud Platform สำหรับแอป DigiHealth AI Patient

---

## Part 1: Google Cloud Platform Setup

### Step 1: Create a Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Sign in with your Google Account
3. Click on the project dropdown at the top (next to "Google Cloud")
4. Click "NEW PROJECT"
5. Enter project name: `digihealthai-patient` (or any name you prefer)
6. Click "CREATE"
7. Wait for the project to be created (this may take a minute)
8. Make sure the new project is selected in the dropdown

### Step 2: Enable Required APIs

You need to enable several APIs: Google Drive API, Google Sheets API, and for Voice Mode: Speech-to-Text API and Text-to-Speech API.

#### Enable Google Sheets API:
1. In the Google Cloud Console, click the hamburger menu (☰) at top-left
2. Navigate to: **APIs & Services** > **Library**
3. In the search bar, type: "Google Sheets API"
4. Click on "Google Sheets API"
5. Click the blue **ENABLE** button
6. Wait for it to be enabled

#### Enable Google Drive API:
1. Still in the API Library, click "API Library" in the breadcrumb or search again
2. In the search bar, type: "Google Drive API"
3. Click on "Google Drive API"
4. Click the blue **ENABLE** button
5. Wait for it to be enabled

#### Enable Speech-to-Text API (for Voice Mode):
1. Still in the API Library, search for: "Cloud Speech-to-Text API"
2. Click on "Cloud Speech-to-Text API"
3. Click the blue **ENABLE** button
4. Wait for it to be enabled

#### Enable Text-to-Speech API (for Voice Mode):
1. Still in the API Library, search for: "Cloud Text-to-Speech API"
2. Click on "Cloud Text-to-Speech API"
3. Click the blue **ENABLE** button
4. Wait for it to be enabled

**Note**: Voice Mode requires both Speech-to-Text and Text-to-Speech APIs to be enabled. The service account with Editor role will have sufficient permissions for these APIs.

### Step 3: Create a Service Account

A Service Account is like a special "robot account" that your app uses to access Google services.

1. Click the hamburger menu (☰) at top-left
2. Navigate to: **APIs & Services** > **Credentials**
3. Click **+ CREATE CREDENTIALS** at the top
4. Select **Service Account**
5. Fill in the details:
   - **Service account name**: `digihealthai-service`
   - **Service account ID**: (auto-generated, leave it)
   - **Description**: "Service account for DigiHealth AI Patient app"
6. Click **CREATE AND CONTINUE**
7. For "Grant this service account access to project":
   - Click the "Select a role" dropdown
   - Choose: **Basic** > **Editor**
   - (This gives the account permission to create and edit files)
8. Click **CONTINUE**
9. Skip the third step (Grant users access) by clicking **DONE**

### Step 4: Create and Download the JSON Key

This is the most important step! The JSON file contains the credentials your app needs.

1. You should now see your service account in the list
2. Click on the service account email (it looks like: `digihealthai-service@your-project.iam.gserviceaccount.com`)
3. Go to the **KEYS** tab at the top
4. Click **ADD KEY** > **Create new key**
5. Choose **JSON** format
6. Click **CREATE**
7. A JSON file will automatically download to your computer
8. **IMPORTANT**: Rename this file to something simple like `gcp-credentials.json`
9. **IMPORTANT**: Keep this file safe and NEVER share it publicly!

### Step 5: Note Your Service Account Email

You will need this email later:
1. Copy the service account email (from Step 4, #2)
2. It looks like: `digihealthai-service@your-project.iam.gserviceaccount.com`
3. Save it in a text file for now

---

## Part 2: Get Google Gemini API Key

### Step 1: Go to Google AI Studio

1. Visit [Google AI Studio](https://aistudio.google.com/)
2. Sign in with your Google Account

### Step 2: Create an API Key

1. Click on **"Get API Key"** in the left sidebar (or top-right)
2. If you have multiple projects, select your `digihealthai-patient` project
3. Click **"Create API Key"**
4. Copy the API key (it looks like: `AIzaSyXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX`)
5. Save it in a text file for now
6. **IMPORTANT**: Keep this key safe and NEVER share it publicly!

---

## Part 3: Configure Secrets for Local Testing

Before deploying to Streamlit Cloud, you should test locally.

### Step 1: Create Secrets Folder

1. In your project folder, create a folder named `.streamlit`
2. Inside `.streamlit`, create a file named `secrets.toml`
3. Your structure should look like:
   ```
   digihealthaipatient/
   ├── .streamlit/
   │   └── secrets.toml
   ├── app.py
   ├── requirements.txt
   └── GUIDE_GCP_SETUP.md
   ```

### Step 2: Open the JSON File

1. Open the `gcp-credentials.json` file you downloaded in a text editor
2. It will look something like this:

```json
{
  "type": "service_account",
  "project_id": "your-project-id",
  "private_key_id": "abc123...",
  "private_key": "-----BEGIN PRIVATE KEY-----\nMIIE...",
  "client_email": "digihealthai-service@your-project.iam.gserviceaccount.com",
  "client_id": "1234567890",
  "auth_uri": "https://accounts.google.com/o/oauth2/auth",
  "token_uri": "https://oauth2.googleapis.com/token",
  "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
  "client_x509_cert_url": "https://www.googleapis.com/..."
}
```

### Step 3: Convert JSON to TOML Format

Open your `.streamlit/secrets.toml` file and paste this template:

```toml
# Gemini API Key
GEMINI_API_KEY = "YOUR_GEMINI_API_KEY_HERE"

# Google Cloud Service Account Credentials
[gcp_service_account]
type = "service_account"
project_id = "your-project-id"
private_key_id = "your-private-key-id"
private_key = """-----BEGIN PRIVATE KEY-----
YOUR PRIVATE KEY HERE (multiple lines)
-----END PRIVATE KEY-----
"""
client_email = "your-service-account@your-project.iam.gserviceaccount.com"
client_id = "your-client-id"
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
client_x509_cert_url = "https://www.googleapis.com/robot/v1/metadata/x509/your-email"
```

### Step 4: Fill in the Values

Now, copy the values from your JSON file to the TOML file:

1. Replace `YOUR_GEMINI_API_KEY_HERE` with your actual Gemini API key
2. Copy `project_id` from JSON to TOML
3. Copy `private_key_id` from JSON to TOML
4. Copy the entire `private_key` (including BEGIN and END lines) - keep it in triple quotes
5. Copy `client_email` from JSON to TOML
6. Copy `client_id` from JSON to TOML
7. Copy `client_x509_cert_url` from JSON to TOML

**Important Note about private_key**:
- The private key should stay in triple quotes `"""`
- Keep all the `\n` characters as they are
- The key should look like one long line with `\n` in it, OR multiple lines between the triple quotes

### Step 5: Save and Test

1. Save the `secrets.toml` file
2. **NEVER commit this file to Git** (it's already in .gitignore)
3. Test locally by running: `streamlit run app.py`

---

## Part 4: Deploy to Streamlit Community Cloud

### Step 1: Push Code to GitHub

1. Create a **private** GitHub repository
2. Push your code (make sure `.streamlit/secrets.toml` is NOT included thanks to `.gitignore`)
3. Only these files should be in your repo:
   - `app.py`
   - `requirements.txt`
   - `.gitignore`
   - `GUIDE_GCP_SETUP.md` (optional)

### Step 2: Deploy on Streamlit Cloud

1. Go to [share.streamlit.io](https://share.streamlit.io/)
2. Sign in with your GitHub account
3. Click **"New app"**
4. Select:
   - Repository: Your GitHub repo
   - Branch: `main` (or `master`)
   - Main file path: `app.py`
5. Click **"Advanced settings"** before deploying

### Step 3: Add Secrets to Streamlit Cloud

This is the critical step!

1. In the "Secrets" section, paste the ENTIRE content of your `secrets.toml` file
2. It should look exactly like your local file:

```toml
GEMINI_API_KEY = "AIzaSyXXXXXXXXX..."

[gcp_service_account]
type = "service_account"
project_id = "your-project-id"
private_key_id = "..."
private_key = """-----BEGIN PRIVATE KEY-----
...
-----END PRIVATE KEY-----
"""
client_email = "..."
client_id = "..."
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
client_x509_cert_url = "..."
```

3. Click **"Save"**
4. Click **"Deploy!"**
5. Wait for the app to deploy (this may take 2-3 minutes)

---

## Part 5: Verify Everything Works

### Test the Application:

1. Once deployed, click through the app:
   - Enter name and email
   - Select Case A
   - Start the text mode simulation
   - Send a message to the AI patient
2. End the case and save the data
3. Check if a new Google Sheet was created

### Check Google Sheets:

1. Go to [Google Drive](https://drive.google.com/)
2. You should see a new file named: `DigiHealth_YourName_TIMESTAMP`
3. Open it to verify the chat data was saved

---

## Troubleshooting / แก้ไขปัญหา

### Problem: "Error loading Google credentials"

**Solution:**
- Check that your `secrets.toml` is correctly formatted
- Make sure all fields from the JSON are copied correctly
- Verify the `private_key` is in triple quotes

### Problem: "Error initializing Gemini"

**Solution:**
- Check that `GEMINI_API_KEY` is correctly added to secrets
- Verify the API key is valid (you can test it at Google AI Studio)
- Make sure there are no extra spaces or quotes

### Problem: "Error creating Google Sheet"

**Solution:**
- Verify both Google Drive API and Google Sheets API are enabled
- Check that the service account has Editor role
- Make sure the `private_key` in secrets is complete and properly formatted

### Problem: Can't see the created Google Sheet

**Solution:**
- The sheet is created under the service account, not your personal account
- The sheet should be set to "anyone with link can view"
- Check the URL returned by the app - it should work

---

## Security Reminders / เตือนความปลอดภัย

1. ✅ **NEVER** commit `secrets.toml` to Git
2. ✅ **NEVER** share your JSON credentials file
3. ✅ **NEVER** share your Gemini API key
4. ✅ Use a **private** GitHub repository for your app
5. ✅ The `.gitignore` file already protects you, but be careful

---

## Need Help? / ต้องการความช่วยเหลือ?

If you encounter issues:

1. Check the Streamlit Cloud logs (available in your dashboard)
2. Verify all API keys and credentials are correct
3. Make sure all APIs are enabled in Google Cloud Console
4. Double-check the formatting of `secrets.toml`

---

## Summary Checklist / สรุปขั้นตอน

- [ ] Created Google Cloud Project
- [ ] Enabled Google Sheets API
- [ ] Enabled Google Drive API
- [ ] Enabled Cloud Speech-to-Text API (for Voice Mode)
- [ ] Enabled Cloud Text-to-Speech API (for Voice Mode)
- [ ] Created Service Account with Editor role
- [ ] Downloaded JSON credentials file
- [ ] Got Gemini API Key from Google AI Studio
- [ ] Created `.streamlit/secrets.toml` locally
- [ ] Tested app locally
- [ ] Pushed code to private GitHub repo
- [ ] Deployed to Streamlit Cloud
- [ ] Added secrets to Streamlit Cloud
- [ ] Tested the deployed app
- [ ] Verified Google Sheet creation works
- [ ] Tested Voice Mode (if using)

---

## Example: Complete secrets.toml Template

Here's a complete example (with fake data - replace with your real data):

```toml
# Google Gemini AI API Key
GEMINI_API_KEY = "AIzaSyABCDEF1234567890_ExampleKeyOnly"

# Google Cloud Platform Service Account Credentials
[gcp_service_account]
type = "service_account"
project_id = "digihealthai-patient-123456"
private_key_id = "a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0"
private_key = """-----BEGIN PRIVATE KEY-----
MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQC... (many lines)
...
-----END PRIVATE KEY-----
"""
client_email = "digihealthai-service@digihealthai-patient-123456.iam.gserviceaccount.com"
client_id = "123456789012345678901"
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
client_x509_cert_url = "https://www.googleapis.com/robot/v1/metadata/x509/digihealthai-service%40digihealthai-patient-123456.iam.gserviceaccount.com"
```

**Remember**: Replace all values with your actual credentials!

---

Good luck with your DigiHealth AI Patient application! 🏥✨

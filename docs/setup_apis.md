# Google Calendar API Setup Guide

## Setup Instructions

1. **Create Google Cloud Project**:
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Create a new project or select existing one
   - Enable Google Calendar API

2. **Create Credentials**:
   - Go to "APIs & Services" > "Credentials"
   - Click "Create Credentials" > "OAuth 2.0 Client IDs"
   - Choose "Desktop application"
   - Download the JSON file as `credentials.json`
   - Place it in your project root

3. **Environment Variables**:
   ```bash
   GOOGLE_CREDENTIALS_PATH=credentials.json
   GOOGLE_TOKEN_PATH=token.json
   ```

4. **First Run**:
   - The first time you use calendar features, a browser window will open
   - Authorize the application
   - A `token.json` file will be created automatically

## Installation

Install the Google Calendar dependencies:

```bash
uv add google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client
```

## Testing

**Test Calendar Integration**:
- Try booking a call through the chat interface
- Check if calendar event is created in your Google Calendar
- Verify the meeting link is generated

## Troubleshooting

### Google Calendar Issues
- Ensure `credentials.json` is in the correct location
- Check that Google Calendar API is enabled
- Verify OAuth consent screen is configured
- Make sure you have sufficient permissions for calendar access

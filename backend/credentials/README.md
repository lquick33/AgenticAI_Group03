# Google Cloud Credentials Setup

This directory is for storing Google Cloud service account credentials used for Text-to-Speech (TTS) functionality.

## ⚠️ Security Notice

**NEVER commit credential files to git!** This directory is already in `.gitignore`.

## Quick Setup Options

### Option 1: Shared Credentials (Team Setup)

If you're working with a small team (2-3 developers), you can share the same service account JSON file:

1. **Get the credentials file** from your teammate via a secure channel (not git!)
   - Use encrypted file sharing (e.g., password-protected zip, secure messaging)
   - Or use a shared secure location (password manager, encrypted drive)

2. **Place the file** in this directory:
   ```bash
   backend/credentials/your-service-account-key.json
   ```

3. **Update your `.env` file** (in project root):
   ```env
   GOOGLE_APPLICATION_CREDENTIALS=backend/credentials/your-service-account-key.json
   ```
   
   Or use absolute path:
   ```env
   GOOGLE_APPLICATION_CREDENTIALS=/full/path/to/backend/credentials/your-service-account-key.json
   ```

4. **Test the setup**:
   ```bash
   cd backend
   source venv/bin/activate
   python test_tts.py
   ```

### Option 2: Individual Setup (Recommended for 3rd Party Testing)

If you're testing the application independently or want your own credentials:

1. **Create a Google Cloud Project** (if you don't have one):
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Create a new project or select an existing one

2. **Enable Text-to-Speech API**:
   - Navigate to: APIs & Services > Library
   - Search for "Cloud Text-to-Speech API"
   - Click "Enable"

3. **Create a Service Account**:
   - Go to: IAM & Admin > Service Accounts
   - Click "Create Service Account"
   - Give it a name (e.g., "tts-service")
   - Click "Create and Continue"

4. **Grant Permissions**:
   - Role: "Cloud Text-to-Speech API User" (or "Editor" for broader access)
   - Click "Continue" then "Done"

5. **Create and Download Key**:
   - Click on your newly created service account
   - Go to "Keys" tab
   - Click "Add Key" > "Create new key"
   - Choose "JSON" format
   - Download the JSON file

6. **Place the file** in this directory:
   ```bash
   backend/credentials/my-service-account-key.json
   ```

7. **Update your `.env` file**:
   ```env
   GOOGLE_APPLICATION_CREDENTIALS=backend/credentials/my-service-account-key.json
   ```

8. **Test the setup**:
   ```bash
   cd backend
   source venv/bin/activate
   python test_tts.py
   ```

## File Structure

```
backend/
  credentials/
    README.md                    # This file
    your-service-account-key.json  # Your credentials (gitignored)
```

## Troubleshooting

### "Credentials not found" error
- Check that the path in `.env` is correct (relative or absolute)
- Verify the file exists at that location
- Make sure there are no typos in the path

### "Permission denied" error
- Ensure the service account has "Cloud Text-to-Speech API User" role
- Check that the Text-to-Speech API is enabled in your Google Cloud project

### "Invalid credentials" error
- Verify the JSON file is valid (not corrupted)
- Make sure you downloaded the complete JSON file
- Check that the service account hasn't been deleted

### Test TTS functionality
```bash
cd backend
source venv/bin/activate
python test_tts.py
```

Expected output: All 5 tests should pass, and MP3 files will be generated in `backend/test_outputs/`

## Cost Information

Google Cloud Text-to-Speech API has a free tier:
- **Free**: First 0-4 million characters per month
- **Paid**: $4.00 per 1 million characters after free tier

For development and testing, the free tier is usually sufficient.

## Additional Resources

- [Google Cloud Text-to-Speech Documentation](https://cloud.google.com/text-to-speech/docs)
- [Service Account Best Practices](https://cloud.google.com/iam/docs/best-practices-service-accounts)
- [API Pricing](https://cloud.google.com/text-to-speech/pricing)

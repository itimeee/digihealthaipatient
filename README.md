# DigiHealth AI Patient 🏥

A web application for training psychiatric residents on patient history taking skills.

## Features

- **Multi-page Flow**: Login → Case Selection → Pre-brief → Chat Simulation → Results
- **AI-Powered Patient**: Uses Google Gemini AI to simulate realistic patient responses
- **Timer System**: 30-minute countdown timer for realistic interview practice
- **Data Logging**: Automatically saves session data to Google Sheets
- **Clean UI**: Professional, minimalist design built with Streamlit

## Tech Stack

- **Python** + **Streamlit**: Web application framework
- **Google Gemini AI**: Powers the AI patient responses
- **Google Sheets API**: Stores session data
- **Google Drive API**: Creates and manages sheets

## Quick Start

### 1. Clone the Repository

```bash
git clone <your-repo-url>
cd digihealthaipatient
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Secrets

1. Create a `.streamlit` folder in the project root
2. Copy `secrets.toml.example` to `.streamlit/secrets.toml`
3. Follow the detailed setup guide in `GUIDE_GCP_SETUP.md` to:
   - Create Google Cloud Project
   - Enable APIs
   - Get Service Account credentials
   - Get Gemini API key
4. Fill in your real credentials in `.streamlit/secrets.toml`

### 4. Run Locally

```bash
streamlit run app.py
```

The app will open in your browser at `http://localhost:8501`

## File Structure

```
digihealthaipatient/
├── app.py                    # Main application code
├── requirements.txt          # Python dependencies
├── .gitignore               # Prevents secrets from being committed
├── GUIDE_GCP_SETUP.md       # Detailed setup instructions
├── secrets.toml.example     # Template for secrets file
└── README.md                # This file
```

## Deployment to Streamlit Cloud

1. Create a **private** GitHub repository
2. Push your code (`.gitignore` will prevent secrets from being uploaded)
3. Go to [share.streamlit.io](https://share.streamlit.io/)
4. Click "New app" and select your repository
5. In "Advanced settings", paste your entire `secrets.toml` content
6. Click "Deploy"

**Important**: Never commit `.streamlit/secrets.toml` or any JSON credential files!

## Configuration

You can easily customize these settings in `app.py`:

```python
# Line 17-18: Change AI Model
MODEL_NAME = "gemini-2.0-flash-exp"

# Line 21-22: Customize AI Patient Behavior
SYSTEM_PROMPT = """Your custom system prompt here..."""

# Line 25: Adjust Timer Duration
TIMER_DURATION_MINUTES = 30

# Line 290-315: Edit Case Information
case_history = """Edit the patient case details here..."""
```

### TTS Model Selection

The application supports selectable TTS (Text-to-Speech) models. The default path is Gemini 2.5 Flash Lite TTS. Configure defaults in `voice_config.py`:

```python
# Default TTS model (Gemini 2.5 Flash Lite TTS)
TTS_MODEL_NAME = "gemini-2.5-flash-lite-preview-tts"
TTS_VOICE_NAME = "th-TH-Neural2-C"

# Optional style prompt to guide the speaking style
TTS_STYLE_PROMPT = ""  # e.g. "Speak in a calm, gentle tone like a patient."
```

**Supported models:**

| Model | Description |
|-------|-------------|
| `gemini-2.5-flash-lite-preview-tts` | Lightweight, fastest (default) |
| `google-cloud-neural2` | Google Cloud TTS with `th-TH-Neural2-C` |
| `google-cloud-standard` | Google Cloud TTS standard voice (`th-TH-Standard-A`) |
| `google-cloud-chirp3-hd` | Google Cloud Chirp3 HD voices (most realistic) |
| `gemini-2.5-flash-preview-tts` | Fast, high-quality (Gemini TTS) |
| `gemini-2.5-pro-preview-tts` | Highest quality, slower |

Users can also select the TTS model, Cloud voice, and Gemini style prompt from the **TTS Settings** panel in the Voice Mode pre-brief page before starting a case. In this app, Gemini TTS requests are forced through the Cloud Text-to-Speech API path.

**Per-request override via `synthesize_speech()`:**

```python
from voice_service import synthesize_speech

# Use default model from config
audio, error = synthesize_speech("Hello world")

# Override model and prompt for a single call
audio, error = synthesize_speech(
    "Hello world",
    model_name="google-cloud-neural2",
    voice_name="th-TH-Neural2-C",
)

# Chirp3 HD (more realistic Cloud TTS voice)
audio, error = synthesize_speech(
    "Hello world",
    model_name="google-cloud-chirp3-hd",
    voice_name="th-TH-Chirp3-HD-Kore",
)

# Gemini TTS override (style prompt applies to Gemini only)
audio, error = synthesize_speech(
    "Hello world",
    model_name="gemini-2.5-pro-preview-tts",
    style_prompt="Speak slowly and clearly.",
)
```

### TTS Requirements

To use Google Cloud TTS and optional Gemini TTS models, ensure the following:

1. **Dependency**: `google-cloud-texttospeech>=2.29.0` (already set in `requirements.txt`)
2. **API enabled**: Enable the **Cloud Text-to-Speech API** in your Google Cloud project
3. **IAM permissions**: The service account needs:
   - `roles/texttospeech.user` (or `textToSpeech.synthesize` permission)
   - For Gemini TTS models, you may also need `aiplatform.endpoints.predict` permission
4. **Billing**: Gemini TTS models require an active billing account on the GCP project

## Usage Guide

### For Students:

1. **Login**: Enter your name and email
2. **Select Case**: Choose from available cases (Case A is active)
3. **Read Pre-brief**: Review patient information and select Text Mode
4. **Conduct Interview**: Chat with the AI patient using the 30-minute timer
5. **End Session**: Click "End Case" when finished
6. **Save Data**: Save your session to Google Sheets for review

### For Administrators:

- Case histories can be edited in `app.py` (lines 290-315)
- System prompts can be modified at the top of `app.py`
- Timer duration is configurable
- Add more cases by following the existing pattern

## Documentation

- **Setup Guide**: See `GUIDE_GCP_SETUP.md` for detailed Google Cloud setup
- **Code Comments**: All code includes bilingual comments (English/Thai)
- **Modular Design**: Each page is a separate function for easy editing

## Security Notes

- ✅ Use a **private** GitHub repository
- ✅ Never commit `.streamlit/secrets.toml`
- ✅ Never share your API keys or credentials
- ✅ The `.gitignore` file protects sensitive files

## Troubleshooting

### "Error loading Google credentials"
- Verify your `secrets.toml` is correctly formatted
- Check that all fields are copied from the JSON file
- Ensure `private_key` is in triple quotes

### "Error initializing Gemini"
- Verify your Gemini API key is correct
- Check for extra spaces or quotes in the key
- Test the key at [Google AI Studio](https://aistudio.google.com/)

### "Error creating Google Sheet"
- Ensure Google Drive and Sheets APIs are enabled
- Verify service account has Editor role
- Check that `private_key` is complete

For more troubleshooting help, see `GUIDE_GCP_SETUP.md`.

## Support

If you encounter issues:
1. Check the Streamlit Cloud logs (if deployed)
2. Verify all credentials in `secrets.toml`
3. Ensure all APIs are enabled in Google Cloud Console
4. Review the setup guide carefully

## License

This project is for educational purposes.

## Credits

Built with ❤️ for psychiatric education

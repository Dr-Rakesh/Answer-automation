from fastapi import FastAPI, File, UploadFile, Form
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
import pandas as pd
import requests
import os
import re
import json
from datetime import datetime
import logging

# Initialize FastAPI app
app = FastAPI()

# Logging configuration
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("app.log"),  # Save logs to 'app.log'
        logging.StreamHandler()         # Print logs to the console
    ]
)
logger = logging.getLogger(__name__)

# Mount static folder
app.mount("/static", StaticFiles(directory="static"), name="static")

# Ensure the output directories exist
os.makedirs("messages", exist_ok=True)
os.makedirs("urls", exist_ok=True)
os.makedirs("output", exist_ok=True)


def extract_urls_from_response(response_text: str) -> list:
    """Extract unique URLs from the 'Relevant URLs' section of the API response."""
    split_text = response_text.split("Relevant URLs:")
    if len(split_text) < 2:
        logger.info("No 'Relevant URLs' section found in response.")
        return []
    urls_section = split_text[1]
    url_pattern = r'<a href=["\']([^"\']+)["\']'
    urls = re.findall(url_pattern, urls_section)
    logger.info(f"Extracted {len(set(urls))} unique URLs.")
    return list(set(urls))


def save_message_to_file(response_json, question, product, version):
    """Save the API response to a JSON file."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    sanitized_question = "".join([c if c.isalnum() else "_" for c in question])[:30]
    filename = f"{sanitized_question}_{timestamp}.json"
    file_path = os.path.join("messages", filename)

    message_text = response_json.get("message", "")
    response_with_metadata = {
        "question": question,
        "product": product,
        "version": version,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "response_raw": response_json,
        "response_message": message_text,
    }

    with open(file_path, "w", encoding="utf-8") as file:
        json.dump(response_with_metadata, file, indent=2)

    logger.info(f"Message saved to {file_path}")
    return file_path


@app.post("/upload-file/")
async def process_file(
    file: UploadFile = File(...),
    product: str = Form(...),
    version: str = Form(...),
):
    """Process the uploaded file and return a processed version."""
    try:
        logger.info(f"Received file: {file.filename}")
        logger.info(f"Selected product: {product}, version: {version}")

        # Save the uploaded file
        input_filepath = f"output/{file.filename}"
        with open(input_filepath, "wb") as f:
            f.write(file.file.read())
        logger.info(f"Uploaded file saved to {input_filepath}")

        # Determine file type and load into a DataFrame
        ext = os.path.splitext(file.filename)[1].lower()
        if ext == ".xlsx":
            df = pd.read_excel(input_filepath)
        elif ext == ".csv":
            df = pd.read_csv(input_filepath)
        else:
            logger.error("Unsupported file format.")
            return {"error": "Unsupported file format. Upload Excel or CSV files."}

        # Ensure required columns are present
        if "Question" not in df.columns:
            logger.error("Missing 'Question' column in the file.")
            return {"error": "The uploaded file must contain a 'Question' column."}

        # Prepare evaluation metric columns
        evaluation_metrics = [
            "Relevance",
            "Accuracy",
            "Clarity",
            "Tone and Politeness",
            "Completeness",
            "Engagement",
            "User Satisfaction",
            "Bias and Ethical",
            "Cross-Session Continuity",
            "Information Provenance"
        ]

        for metric in evaluation_metrics:
            if metric not in df.columns:
                df[metric] = ""
                logger.info(f"Added column: {metric}")

        # Prepare columns for results
        if "Extracted Text" not in df.columns:
            df["Extracted Text"] = ""
            logger.info("Added column: Extracted Text")
        if "Extracted URL" not in df.columns:
            df["Extracted URL"] = ""
            logger.info("Added column: Extracted URL")

        # API endpoint
        api_url = "https://app-adt-02.azurewebsites.net/api/message"

        # Process each question
        for index, row in df.iterrows():
            question = row.get("Question", "")
            if not pd.isna(question) and question.strip():
                logger.info(f"Processing question {index + 1}/{len(df)}: {question}")
                payload = {"question": question, "product": product, "version": version}

                try:
                    response = requests.post(api_url, json=payload, timeout=60)
                    if response.status_code == 200:
                        response_json = response.json()
                        response_text = response_json.get("message", "")
                        extracted_urls = extract_urls_from_response(response_text)

                        # Update DataFrame
                        df.at[index, "Extracted Text"] = response_text
                        df.at[index, "Extracted URL"] = "\n".join(extracted_urls) if extracted_urls else "No URL found"

                        # Save response and URLs
                        save_message_to_file(response_json, question, product, version)
                        logger.info(f"Processed question {index + 1} successfully.")
                    else:
                        logger.warning(f"API request failed for question {index + 1}: {response.status_code}")
                        df.at[index, "Extracted Text"] = "Error: Failed to get response from API"
                        df.at[index, "Extracted URL"] = "No URL found"
                except requests.exceptions.RequestException as e:
                    logger.error(f"Request exception for question {index + 1}: {e}")
                    df.at[index, "Extracted Text"] = "Error: API request failed"
                    df.at[index, "Extracted URL"] = "No URL found"

        # Save the processed file
        output_filename = f"processed_{datetime.now().strftime('%Y%m%d_%H%M%S')}{ext}"
        output_filepath = f"output/{output_filename}"
        if ext == ".xlsx":
            df.to_excel(output_filepath, index=False)
        else:
            df.to_csv(output_filepath, index=False)
        logger.info(f"Processed file saved to {output_filepath}")

        return FileResponse(output_filepath, filename=output_filename)

    except Exception as e:
        logger.error(f"An error occurred: {e}")
        return {"error": str(e)}


@app.get("/", response_class=HTMLResponse)
async def serve_frontend():
    """Serve the main HTML page."""
    try:
        with open("static/index.html", "r") as file:
            return HTMLResponse(content=file.read())
    except FileNotFoundError:
        logger.error("Frontend index.html not found.")
        return HTMLResponse(content="<h1>Error: Frontend files not found</h1>", status_code=500)
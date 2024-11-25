from flask import Flask, request, jsonify
import openai
import os
import json
import ast
from io import BytesIO
import requests
import cv2
import numpy as np
from moviepy.editor import ImageClip, concatenate_videoclips, VideoFileClip, AudioFileClip, ImageSequenceClip
from moviepy.video.fx.all import resize, crop
import boto3
from botocore.exceptions import NoCredentialsError
from PIL import Image
from urllib.request import urlopen, urlretrieve
import uuid
import re
from elevenlabs import ElevenLabs
import pandas as pd

elevenlabs = ElevenLabs(api_key=os.getenv("ELEVENLABS_API_KEY"))

app = Flask(__name__)
openai_api_key = os.getenv("OPENAI_API_KEY")

# Initialize the OpenAI client
client = openai.OpenAI(api_key=openai_api_key)

# Defining AWS credentials
aws_region = os.getenv("AWS_REGION")
aws_access_key = os.getenv("AWS_ACCESS_KEY")
aws_secret_key = os.getenv("AWS_SECRET_KEY")
bucket_name = os.getenv("S3_BUCKET_NAME")

# Upload file to S3
def upload_file_to_s3(file_path, bucket_name, s3_filename):
    s3 = boto3.client('s3',
                      region_name=aws_region,
                      aws_access_key_id=aws_access_key,
                      aws_secret_access_key=aws_secret_key)
    try:
        # Generate a unique filename if not provided
        if s3_filename is None:
            unique_id = uuid.uuid4().hex
            s3_filename = f"sound_effect_library_{unique_id}.mp3"
        
        s3.upload_file(file_path, bucket_name, s3_filename)
        s3_url = f"https://{bucket_name}.s3.{aws_region}.amazonaws.com/{s3_filename}"
        print(f"File uploaded to {s3_url}")
        return s3_url
    except FileNotFoundError:
        print("The file was not found")
        return None
    except NoCredentialsError:
        print("Credentials not available")
        return None

# Generating text using OpenAI GPT-4 API
def generate_text(topic):
    completion = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You job is to create simple line propmts for sound effects"},
            {"role": "user", "content": f"You job is to create 25 prompts about {topic} which will be used to create sound effects. Keep the prompts extremely short and simple. And give in the form of a numbered list 1. 2. a and nothing else"}
        ]
    )
    response = completion.choices[0].message.content
    return str(response)

# Generate sound effect and save to local path
def generate_sound_effect(text: str):
    unique_id = uuid.uuid4().hex
    output_path = f"testing_sound_effects/output_{unique_id}.mp3"
    folder_path = "testing_sound_effects"
    os.makedirs(folder_path, exist_ok=True)
    
    print("Generating sound effects...")
    result = elevenlabs.text_to_sound_effects.convert(
        text=text,
        duration_seconds=1,
        prompt_influence=0.3,
    )

    with open(output_path, "wb") as f:
        for chunk in result:
            f.write(chunk)
    print(f"Audio saved to {output_path}")
    return output_path

# Update Excel sheet
def update_excel_sheet(prompt, s3_url, sheet_path="sound_effects.xlsx"):
    # Create DataFrame if file doesn't exist
    if not os.path.exists(sheet_path):
        df = pd.DataFrame(columns=["Prompt", "S3 URL"])
    else:
        # Load existing DataFrame
        df = pd.read_excel(sheet_path)
    
    # Append new row
    new_row = pd.DataFrame([{"Prompt": prompt, "S3 URL": s3_url}])
    df = pd.concat([df, new_row], ignore_index=True)

    
    # Save updated DataFrame to Excel
    df.to_excel(sheet_path, index=False)
    print(f"Excel sheet updated: {sheet_path}")

# Inputs
topic = input("Enter the topic: ")

# Creating prompts for sound effects using GPT
prompts_str = generate_text(topic)
prompts_list = [re.sub(r"^\d+\.\s*", "", line).strip() for line in prompts_str.split('\n')]
print("Generated Prompts:", prompts_list)

# Creating sound effects and processing each prompt
for prompt in prompts_list:
    local_audio_path = generate_sound_effect(prompt)  # Generate sound effect
    s3_audio_url = upload_file_to_s3(local_audio_path, bucket_name, None)  # Upload to S3
    if s3_audio_url:
        update_excel_sheet(prompt, s3_audio_url)  # Update Excel sheet


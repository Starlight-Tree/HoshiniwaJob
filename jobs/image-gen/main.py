import os
from google import genai
from google.genai import types

def main():
    project_id = os.environ.get("GOOGLE_CLOUD_PROJECT", "imagen-app-2026")
    location = os.environ.get("GOOGLE_CLOUD_LOCATION", "global")
    task_index = os.environ.get("CLOUD_RUN_TASK_INDEX", "0")

    print(f"Initializing GenAI Client for project: {project_id} in {location} (Task #{task_index})")
    client = genai.Client(vertexai=True, project=project_id, location=location)

    prompt = os.environ.get(
        "IMAGE_PROMPT",
        "A futuristic cyberpunk Tokyo street at night, highly detailed"
    )
    print(f"Generating image with Nano Banana 2 Lite: '{prompt}'")

    response = client.models.generate_content(
        model="gemini-3.1-flash-lite-image",  # Nano Banana 2 Lite
        contents=prompt,
        config=types.GenerateContentConfig(
            response_modalities=["IMAGE"],
            image_config=types.ImageConfig(
                aspect_ratio="1:1",
            ),
        ),
    )

    image_count = 0
    for part in response.candidates[0].content.parts:
        if part.inline_data and part.inline_data.data:
            image_bytes = part.inline_data.data
            filename = f"output_task{task_index}_{image_count}.png"
            with open(filename, "wb") as f:
                f.write(image_bytes)
            print(f"Saved Nano Banana 2 Lite image to {filename}")
            image_count += 1

    if image_count == 0:
        print("Warning: No images were returned.")

if __name__ == "__main__":
    main()

import os
import json
import base64
import io
from dotenv import load_dotenv
from PIL import Image
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

load_dotenv()


def generate_image_title_dscrpt(image_path):
    """
    Generate image title and description using OpenAI Vision API.
    Replaces the old Gemini-based implementation.
    """
    openai_api_key = os.environ.get("OPENAI_API_KEY")
    
    if not openai_api_key:
        print("Warning: OPENAI_API_KEY not configured. Returning default image metadata.")
        return {
            "title": "Untitled",
            "description": "Image description not available (OpenAI API not configured)"
        }
    
    try:
        # Initialize OpenAI client
        llm = ChatOpenAI(
            model="gpt-4o-mini",  # Using vision-capable model
            temperature=0.7,
            max_retries=3,
            timeout=30,
            api_key=openai_api_key
        )
        
        # Read and encode image
        img = Image.open(image_path)
        img_byte_arr = io.BytesIO()
        img.convert("RGB").save(img_byte_arr, format='JPEG')
        img_base64 = base64.b64encode(img_byte_arr.getvalue()).decode("utf-8")
        
        # Build message with image
        message_content = [
            {
                "type": "text",
                "text": """Analyze this image and provide a title and short description in JSON format:
{
    "title": "title of image",
    "description": "short description of image"
}

Return only valid JSON, no markdown formatting."""
            },
            {
                "type": "image_url",
                "image_url": f"data:image/jpeg;base64,{img_base64}"
            }
        ]
        
        message = HumanMessage(content=message_content)
        response = llm.invoke([message])
        
        # Extract and parse JSON from response
        response_text = response.content if hasattr(response, "content") else str(response)
        
        # Clean JSON string (remove markdown code blocks if present)
        json_str = response_text.replace('```json', '').replace('```', '').strip()
        
        # Parse JSON
        result = json.loads(json_str)
        return {
            "title": result.get("title", "Untitled"),
            "description": result.get("description", "No description"),
        }
        
    except json.JSONDecodeError as e:
        print(f"JSON Error: {e}\nResponse was: {response_text}")
        return {
            "title": "Untitled",
            "description": "No description available",
            "error": f"Invalid JSON: {str(e)}",
            "raw_response": response_text
        }
    except Exception as e:
        print(f"Error generating image description: {str(e)}")
        return {
            "title": "Untitled",
            "description": "No response from API",
            "error": str(e)
        }


if __name__ == "__main__":
    result = generate_image_title_dscrpt(
        r"C:\Users\rajsu\OneDrive\Pictures\Screenshots\Screenshot 2025-01-30 120555.png")
    print(result)

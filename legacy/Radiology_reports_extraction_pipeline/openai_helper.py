import os

from openai import OpenAI
from extraction_prompt_diagnostic_PET import data_extraction_prompt

client = OpenAI(
  api_key=os.getenv("OPENAI_API_KEY", "")
)

def extract_data(report, max_retries=3, initial_wait=5):
    """
    Extract data from the provided report, using an OpenAI responses API call.
    If the API call fails, it will attempt retries with exponential backoff.

    :param report: The content to be processed.
    :param max_retries: The maximum number of attempts before raising an error.
    :param initial_wait: The initial wait time (in seconds) before the first retry.
    :return: The content of the completion response.
    """
    import time

    wait_time = initial_wait
    for attempt in range(1, max_retries + 1):
        try:
            response = client.responses.create(
                model="gpt-5.2",
                input=[
                    {
                        "role": "system",
                        "content": [
                            {
                                "type": "input_text",
                                "text": data_extraction_prompt
                            }
                        ]
                    },
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "input_text",
                                "text": report
                            }
                        ]
                    }
                ],
                text={
                    "format": {
                        "type": "json_object"
                    }
                },
                reasoning={},
                tools=[],
                temperature=0.36,
                max_output_tokens=3992,
                top_p=1,
                store=True
            )
            return response.output[0].content[0].text

        except Exception as e:
            # If it's not the last attempt, wait and try again.
            if attempt < max_retries:
                print(f"Attempt {attempt} failed. Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
                # Simple exponential backoff strategy
                wait_time *= 2
            else:
                # Last attempt did not succeed; raise the exception
                raise e

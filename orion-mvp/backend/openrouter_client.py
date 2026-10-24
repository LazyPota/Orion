"""
Project ORION - OpenRouter Multimodal VLM Client & Dual Action Parser
Communicates with OpenRouter API using nvidia/nemotron-3.5-super-vl:free.
Includes resilient dual parser handling native tool_calls, markdown JSON, or raw text.
"""

import json
import re
from typing import Any, Dict, List, Optional

import httpx

from .schemas import AgentAction
from config import config


def parse_agent_response(response_data: Dict[str, Any]) -> AgentAction:
    """
    Resilient Dual Action Parser:
    Extracts structured thought, action, args, summary_for_user, and spoken_response
    whether the model responds via native tool_calls, markdown ```json code blocks,
    or inline JSON.
    """
    try:
        choices = response_data.get("choices", [])
        if not choices:
            return AgentAction(
                thought="No completion choices returned by model.",
                action="answer_only",
                args={"message": "I apologize, Sir, but I received an empty response from the vision model."},
                summary_for_user="No response from VLM.",
                spoken_response=f"I beg your pardon, {config.ORION_USER_TITLE}, but the vision model returned no response.",
            )

        message = choices[0].get("message", {})

        # 1. Check for native OpenAI tool_calls
        tool_calls = message.get("tool_calls", [])
        if tool_calls:
            call = tool_calls[0]
            func = call.get("function", {})
            name = func.get("name", "answer_only")
            raw_args = func.get("arguments", "{}")
            parsed_args = {}
            try:
                parsed_args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
            except Exception:
                parsed_args = {"raw_arguments": raw_args}

            thought = message.get("content") or "Invoking tool call from VLM."
            summary = parsed_args.get("summary_for_user", f"Executing ACI tool: {name}")
            spoken = parsed_args.get(
                "spoken_response",
                f"Right away, {config.ORION_USER_TITLE}. Executing {name.replace('_', ' ')}.",
            )

            return AgentAction(
                thought=thought,
                action=name,
                args=parsed_args,
                summary_for_user=summary,
                spoken_response=spoken,
            )

        # 2. Inspect text content
        content = message.get("content", "")
        if not content:
            return AgentAction(
                thought="Empty text returned by model.",
                action="answer_only",
                args={"message": "No text generated."},
                summary_for_user="Empty model response.",
                spoken_response=f"I am standing by, {config.ORION_USER_TITLE}.",
            )

        # 2a. Look for ```json ... ``` blocks
        json_pattern = r"```(?:json)?\s*([\s\S]*?)\s*```"
        matches = re.findall(json_pattern, content)
        candidates = matches if matches else [content]

        for cand in candidates:
            cand = cand.strip()
            # Find outermost { ... }
            start_idx = cand.find("{")
            end_idx = cand.rfind("}")
            if start_idx != -1 and end_idx > start_idx:
                json_str = cand[start_idx : end_idx + 1]
                try:
                    obj = json.loads(json_str)
                    if isinstance(obj, dict) and "action" in obj:
                        action_name = obj.get("action", "answer_only")
                        thought = obj.get("thought", "Analyzed visual and workspace context.")
                        args = obj.get("args", {})
                        summary = obj.get("summary_for_user", f"Action: {action_name}")
                        spoken = obj.get(
                            "spoken_response",
                            f"At your service, {config.ORION_USER_TITLE}. Processing request.",
                        )
                        return AgentAction(
                            thought=thought,
                            action=action_name,
                            args=args,
                            summary_for_user=summary,
                            spoken_response=spoken,
                        )
                except Exception:
                    continue

        # 3. Direct JSON parse of entire content
        try:
            obj = json.loads(content.strip())
            if isinstance(obj, dict):
                return AgentAction(
                    thought=obj.get("thought", "Processed request."),
                    action=obj.get("action", "answer_only"),
                    args=obj.get("args", {}),
                    summary_for_user=obj.get("summary_for_user", "Completed action."),
                    spoken_response=obj.get("spoken_response", f"Task complete, {config.ORION_USER_TITLE}."),
                )
        except Exception:
            pass

        # 4. Fallback for conversational plain text
        cleaned_content = content.strip()
        return AgentAction(
            thought="Direct conversational response without tool invocation.",
            action="answer_only",
            args={"message": cleaned_content},
            summary_for_user=cleaned_content[:60] + "..." if len(cleaned_content) > 60 else cleaned_content,
            spoken_response=f"Indeed, {config.ORION_USER_TITLE}. {cleaned_content[:80]}",
        )

    except Exception as e:
        return AgentAction(
            thought=f"Error parsing model response: {str(e)}",
            action="answer_only",
            args={"error": str(e)},
            summary_for_user=f"Parse Error: {str(e)}",
            spoken_response=f"Apologies, {config.ORION_USER_TITLE}, an unexpected error occurred while parsing the response.",
        )


async def query_openrouter_vlm(
    messages: List[Dict[str, Any]],
    temperature: float = 0.0,
    model: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Sends multimodal messages payload to OpenRouter Chat Completions endpoint.
    Includes deterministic fallback mock if API key is not configured.
    """
    chosen_model = model or config.OPENROUTER_MODEL
    api_key = config.OPENROUTER_API_KEY.strip()

    # If no API key configured, provide a helpful mock response for live testing
    if not api_key or api_key.startswith("your-openrouter"):
        return {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "thought": "No OPENROUTER_API_KEY provided in .env. Operating in test sandbox mode.",
                                "action": "open_file",
                                "args": {"path": "buggy_calc.py", "line_start": 1},
                                "summary_for_user": "Previewing buggy_calc.py (API Key required for live VLM)",
                                "spoken_response": f"Good day, {config.ORION_USER_TITLE}. OpenRouter API key is not yet configured, so I am previewing the workspace file in sandbox mode.",
                            }
                        )
                    }
                }
            ]
        }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "HTTP-Referer": "https://github.com/project-orion/orion-aci",
        "X-Title": "Project ORION (Group S.T.A.R.K.)",
        "Content-Type": "application/json",
    }

    payload = {
        "model": chosen_model,
        "temperature": temperature,
        "messages": messages,
    }

    async with httpx.AsyncClient(timeout=45.0) as client:
        response = await client.post(
            config.OPENROUTER_BASE_URL,
            headers=headers,
            json=payload,
        )
        response.raise_for_status()
        return response.json()

#!/usr/bin/env python3
"""
Script to measure AgentCore Runtime latency by comparing client-side timing with CloudWatch logs.
"""

import boto3
import json
import time
import uuid
from datetime import datetime
import argparse

def list_log_streams(log_group_name, region='us-east-1'):
    """
    List all log streams in a CloudWatch log group with their last event times.
    """
    client = boto3.client('logs', region_name=region)
    
    try:
        response = client.describe_log_streams(
            logGroupName=log_group_name,
            orderBy='LastEventTime',
            descending=True
        )
        return [(stream['logStreamName'], stream.get('lastEventTimestamp', 0)) 
                for stream in response.get('logStreams', [])]
    except Exception as e:
        print(f"Error listing log streams: {e}")
        # Try without ordering
        try:
            response = client.describe_log_streams(
                logGroupName=log_group_name
            )
            return [(stream['logStreamName'], stream.get('lastEventTimestamp', 0)) 
                    for stream in response.get('logStreams', [])]
        except Exception as e2:
            print(f"Error listing log streams (fallback): {e2}")
            return []

def get_cloudwatch_logs(log_group_name, log_stream_names, search_term, region='us-east-1'):
    """
    Retrieve CloudWatch logs for a specific search term.
    Checking log group: {log_group_name}
    Checking log streams: {log_stream_names}
    """
    client = boto3.client('logs', region_name=region)
    
    print(f"Checking CloudWatch logs in:")
    print(f"  Log Group: {log_group_name}")
    print(f"  Log Streams: {log_stream_names}")
    print(f"  Search Term: '{search_term}'")
    
    # Filter out any log streams that might not exist
    valid_log_streams = []
    for stream in log_stream_names:
        if 'log_stream_created_by_aws_to_validate_log_delivery_subscriptions' not in stream:
            valid_log_streams.append(stream)
        else:
            print(f"Skipping validation stream: {stream}")
    
    if not valid_log_streams:
        print("No valid log streams to check")
        return []
    else:
        print(f"Valid log streams to check: {valid_log_streams}")
    
    # Try each log stream individually to isolate issues
    all_events = []
    for stream_name in valid_log_streams:
        try:
            print(f"  Trying log stream: {stream_name}")
            # If search term is empty, don't use filterPattern
            if not search_term:
                response = client.filter_log_events(
                    logGroupName=log_group_name,
                    logStreamNames=[stream_name]
                )
            else:
                response = client.filter_log_events(
                    logGroupName=log_group_name,
                    logStreamNames=[stream_name],
                    filterPattern=f'{search_term}'
                )
            
            events = response.get('events', [])
            print(f"    Retrieved {len(events)} events from {stream_name}")
            all_events.extend(events)
        except Exception as e:
            if "ResourceNotFoundException" in str(e) or "log stream does not exist" in str(e):
                print(f"    Resource not found for stream {stream_name}: {e}")
                # Try without specifying the log stream (get all streams)
                try:
                    print(f"    Trying without specifying log stream...")
                    if not search_term:
                        response = client.filter_log_events(
                            logGroupName=log_group_name
                        )
                    else:
                        response = client.filter_log_events(
                            logGroupName=log_group_name,
                            filterPattern=f'{search_term}'
                        )
                    events = response.get('events', [])
                    print(f"    Retrieved {len(events)} events without specifying stream")
                    all_events.extend(events)
                except Exception as e2:
                    print(f"    Error retrieving logs without stream specification: {e2}")
            else:
                print(f"    Error retrieving CloudWatch logs for stream {stream_name}: {e}")
        except Exception as e:
            print(f"    Error retrieving CloudWatch logs for stream {stream_name}: {e}")
    
    return all_events

def get_cloudwatch_logs_no_filter(log_group_name, log_stream_names, region='us-east-1'):
    """
    Retrieve CloudWatch logs without any filter pattern.
    """
    client = boto3.client('logs', region_name=region)
    
    print(f"Checking CloudWatch logs (no filter) in:")
    print(f"  Log Group: {log_group_name}")
    print(f"  Log Streams: {log_stream_names}")
    
    # Filter out any log streams that might not exist
    valid_log_streams = []
    for stream in log_stream_names:
        if 'log_stream_created_by_aws_to_validate_log_delivery_subscriptions' not in stream:
            valid_log_streams.append(stream)
        else:
            print(f"Skipping validation stream: {stream}")
    
    if not valid_log_streams:
        print("No valid log streams to check")
        return []
    else:
        print(f"Valid log streams to check: {valid_log_streams}")
    
    # Try each log stream individually to isolate issues
    all_events = []
    for stream_name in valid_log_streams:
        try:
            print(f"  Trying log stream: {stream_name}")
            response = client.filter_log_events(
                logGroupName=log_group_name,
                logStreamNames=[stream_name]
            )
            
            events = response.get('events', [])
            print(f"    Retrieved {len(events)} events from {stream_name}")
            all_events.extend(events)
        except Exception as e:
            if "ResourceNotFoundException" in str(e) or "log stream does not exist" in str(e):
                print(f"    Resource not found for stream {stream_name}: {e}")
                # Try without specifying the log stream (get all streams)
                try:
                    print(f"    Trying without specifying log stream...")
                    response = client.filter_log_events(
                        logGroupName=log_group_name
                    )
                    events = response.get('events', [])
                    print(f"    Retrieved {len(events)} events without specifying stream")
                    all_events.extend(events)
                except Exception as e2:
                    print(f"    Error retrieving logs without stream specification: {e2}")
            else:
                print(f"    Error retrieving CloudWatch logs for stream {stream_name}: {e}")
        except Exception as e:
            print(f"    Error retrieving CloudWatch logs for stream {stream_name}: {e}")
    
    return all_events

def find_session_logs(log_events, session_id):
    """
    Find logs that contain the specific session ID in their message content.
    """
    matching_events = []
    
    for i, event in enumerate(log_events):
        # Check if the event message contains our session ID
        message_content = event.get('message', '')
        if session_id in message_content:
            print(f"  Found session ID in log event {i}: {message_content[:100]}...")
            matching_events.append(event)
        else:
            # Try to parse JSON message and check for session ID
            try:
                if '"sessionId":' in message_content or '"message":' in message_content:
                    # Extract the message field from the JSON
                    import json
                    log_data = json.loads(message_content)
                    session_id_from_log = log_data.get('sessionId', '')
                    inner_message = log_data.get('message', '')
                    if session_id in session_id_from_log or session_id in inner_message:
                        print(f"  Found session ID in parsed log event {i}: sessionId={session_id_from_log[:50]}..., message={inner_message[:50]}...")
                        matching_events.append(event)
            except Exception as e:
                # If we can't parse as JSON, check if it's a simple message
                if session_id in message_content:
                    print(f"  Found session ID in raw log event {i}: {message_content[:100]}...")
                    matching_events.append(event)
                # Skip parsing errors for now
    
    return matching_events

def find_request_logs(log_events, request_id):
    """
    Find logs that contain the specific request ID in their message content.
    """
    matching_events = []
    
    for event in log_events:
        # Check if the event message contains our request ID
        if request_id in event.get('message', ''):
            matching_events.append(event)
        else:
            # Try to parse JSON message and check for request ID
            try:
                message_content = event.get('message', '')
                if '"message":' in message_content:
                    # Extract the message field from the JSON
                    import json
                    log_data = json.loads(message_content)
                    inner_message = log_data.get('message', '')
                    if request_id in inner_message:
                        matching_events.append(event)
            except:
                # If we can't parse as JSON, skip
                pass
    
    return matching_events

def parse_cloudwatch_event_timestamp(log_event):
    """
    Parse the event_timestamp from a CloudWatch log event.
    """
    try:
        # CloudWatch timestamps are in milliseconds since epoch
        timestamp_ms = log_event['timestamp']
        return timestamp_ms / 1000.0  # Convert to seconds
    except Exception as e:
        print(f"Error parsing timestamp: {e}")
        return None

def calculate_latency_difference(client_start_time, cloudwatch_event_timestamp):
    """
    Calculate the difference between client start time and CloudWatch event timestamp.
    """
    if cloudwatch_event_timestamp:
        difference = cloudwatch_event_timestamp - client_start_time
        return difference
    return None

def main():
    parser = argparse.ArgumentParser(description='Measure AgentCore Runtime latency')
    parser.add_argument('--region', default='us-east-1', help='AWS region')
    parser.add_argument('--agent-runtime-arn', default='arn:aws:bedrock-agentcore:us-east-1:546275881527:runtime/ea_banappeal-dE2x2P736K', 
                       help='Agent Runtime ARN')
    parser.add_argument('--log-group', default='/aws/bedrock-agentcore/runtimes/ea_banappeal-dE2x2P736K-DEFAULT', 
                       help='CloudWatch log group name')
    parser.add_argument('--log-stream', default='BedrockAgentCoreRuntime_ApplicationLogs', 
                       help='CloudWatch log stream name')
    
    args = parser.parse_args()
    
    # Generate a session ID
    session_id = str(uuid.uuid4())
    print(f"Using Session ID: {session_id}")
    
    # Record client-side start time
    client_start_time = time.time()
    client_start_iso = datetime.fromtimestamp(client_start_time).isoformat()
    print(f"Client start time: {client_start_iso}")
    
    # Actually invoke the agent
    print("Invoking the agent...")
    client = boto3.client('bedrock-agentcore', region_name=args.region)
    
    try:
        # Create the payload with the input text
        payload = {
            "prompt": f"Test invocation for latency measurement. Session ID: {session_id}"
        }
        
        response = client.invoke_agent_runtime(
            agentRuntimeArn=args.agent_runtime_arn,
            qualifier='DEFAULT',
            runtimeSessionId=session_id,
            payload=json.dumps(payload),
            contentType='application/json',
            accept='application/json'
        )
        
        print(f"Full invoke response: {json.dumps(response, indent=2, default=str)}")
        
        # Extract request ID from response if available
        request_id = None
        if 'ResponseMetadata' in response and 'RequestId' in response['ResponseMetadata']:
            request_id = response['ResponseMetadata']['RequestId']
            print(f"Extracted Request ID from response: {request_id}")
        elif 'headers' in response and 'x-amzn-requestid' in response['headers']:
            request_id = response['headers']['x-amzn-requestid']
            print(f"Extracted Request ID from headers: {request_id}")
        else:
            # Generate a request ID if not in response
            request_id = str(uuid.uuid4())
            print(f"Generated Request ID: {request_id}")
        
        # Process the response
        completion = ''
        if 'completion' in response:
            # Handle streaming response directly
            try:
                for event in response['completion']:
                    if 'chunk' in event:
                        completion += event['chunk']['bytes'].decode('utf-8')
                
                print(f"Agent response received: {completion[:100]}...")  # Print first 100 chars
            except Exception as e:
                print(f"Error processing completion: {e}")
                print(f"Completion data: {response['completion']}")
        elif 'payload' in response:
            # Handle streaming response
            try:
                # The payload might be a StreamingBody, read it
                if hasattr(response['payload'], 'read'):
                    payload_content = response['payload'].read()
                    payload_data = json.loads(payload_content)
                else:
                    payload_data = response['payload']
                    
                if isinstance(payload_data, dict) and 'completion' in payload_data:
                    for event in payload_data['completion']:
                        if 'chunk' in event:
                            completion += event['chunk']['bytes'].decode('utf-8')
                    
                    print(f"Agent response received: {completion[:100]}...")  # Print first 100 chars
                else:
                    print("Agent invoked successfully")
                    print(f"Payload data: {payload_data}")
            except Exception as e:
                print(f"Error processing payload: {e}")
                print(f"Raw payload: {response['payload']}")
        else:
            print("Agent invoked successfully (no completion or payload data in response)")
            print(f"Response keys: {list(response.keys())}")
        
    except Exception as e:
        print(f"Error invoking agent: {e}")
        print("Continuing with log retrieval...")
    
    # Record client-side end time
    client_end_time = time.time()
    client_end_iso = datetime.fromtimestamp(client_end_time).isoformat()
    client_duration = (client_end_time - client_start_time) * 1000
    print(f"Client end time: {client_end_iso}")
    print(f"Client-side duration: {client_duration:.2f}ms")
    
    # Wait for logs to be written to CloudWatch with retries
    print("Waiting for logs to be written to CloudWatch...")
    log_events = []
    matching_events = []
    max_retries = 12  # Try for up to 60 seconds (12 * 5 seconds)
    retry_count = 0
    
    # Get list of available log streams with timestamps
    print("Listing available log streams...")
    all_log_streams_with_time = list_log_streams(args.log_group, args.region)
    if all_log_streams_with_time:
        print(f"Found {len(all_log_streams_with_time)} log streams:")
        # Filter for streams that match the expected pattern and are recent
        # Also filter out the AWS validation stream
        relevant_streams = []
        client_start_ms = int(client_start_time * 1000)  # Convert to milliseconds
        
        for stream_name, last_event_time in all_log_streams_with_time:
            # Check if it's a recent stream (within last 10 minutes)
            # Also filter out the AWS validation stream
            time_diff = client_start_ms - last_event_time if last_event_time else float('inf')
            is_recent = time_diff < 600000  # Within 10 minutes
            is_validation_stream = 'log_stream_created_by_aws_to_validate_log_delivery_subscriptions' in stream_name
            has_runtime_pattern = 'runtime-logs-' in stream_name and '[' in stream_name and ']' in stream_name
            
            if is_recent and not is_validation_stream:
                relevant_streams.append((stream_name, last_event_time))
                status = "MATCH"
            else:
                status = "SKIP"
                if not is_recent:
                    status += " (too old)"
                if is_validation_stream:
                    status += " (validation stream)"
            
            print(f"  [{status}] {stream_name} (Last event: {datetime.fromtimestamp(last_event_time/1000).isoformat() if last_event_time else 'Unknown'})")
        
        # Sort by most recent first
        relevant_streams.sort(key=lambda x: x[1], reverse=True)
        
        # If we found relevant streams, use those; otherwise fall back to all streams
        if relevant_streams:
            print(f"Found {len(relevant_streams)} relevant log streams (recent and not validation):")
            for stream_name, last_event_time in relevant_streams[:10]:  # Show first 10 streams
                last_event_iso = datetime.fromtimestamp(last_event_time/1000).isoformat() if last_event_time else "Unknown"
                print(f"  - {stream_name} (Last event: {last_event_iso})")
            all_log_streams = [stream_name for stream_name, _ in relevant_streams]
        else:
            print("No recent streams found, using all streams (excluding validation stream):")
            filtered_streams = [(name, time) for name, time in all_log_streams_with_time 
                              if 'log_stream_created_by_aws_to_validate_log_delivery_subscriptions' not in name]
            for stream_name, last_event_time in filtered_streams[:10]:  # Show first 10 streams
                last_event_iso = datetime.fromtimestamp(last_event_time/1000).isoformat() if last_event_time else "Unknown"
                print(f"  - {stream_name} (Last event: {last_event_iso})")
            all_log_streams = [stream_name for stream_name, _ in filtered_streams]
    else:
        print("No log streams found, will use default stream only")
        all_log_streams = [args.log_stream]
    
    while retry_count < max_retries and not matching_events:
        if retry_count > 0:
            print(f"Retry {retry_count}/{max_retries}: Still waiting for logs...")
            time.sleep(5)  # Wait 5 seconds between retries
        
        # Retrieve CloudWatch logs for this session
        print("Retrieving CloudWatch logs...")
        # Check both the specified log stream and all available log streams
        log_stream_names = [args.log_stream] + [s for s in all_log_streams if s != args.log_stream]
        
        # First try without a filter pattern to get all recent logs
        print("Attempting to retrieve logs without filter...")
        log_events = get_cloudwatch_logs_no_filter(args.log_group, log_stream_names, args.region)
        print(f"Retrieved {len(log_events)} events without filter")
        
        # If that fails, try with empty filter pattern
        if not log_events:
            print("Attempting to retrieve logs with empty filter...")
            log_events = get_cloudwatch_logs(args.log_group, log_stream_names, "", args.region)
            print(f"Retrieved {len(log_events)} events with empty filter")
        
        # Find logs that specifically match our session ID
        if log_events:
            print(f"Searching through {len(log_events)} log events for session ID: {session_id}")
            matching_events = find_session_logs(log_events, session_id)
            if matching_events:
                print(f"Found {len(matching_events)} matching log events for session ID {session_id}")
            else:
                # Also try to find request ID matches
                print(f"No matching log events for session ID {session_id}, trying with request ID {request_id}")
                matching_events = find_request_logs(log_events, request_id)
                if matching_events:
                    print(f"Found {len(matching_events)} matching log events for request ID {request_id}")
        else:
            print("No log events retrieved to search through")
        
        retry_count += 1
    
    if not matching_events:
        print(f"No CloudWatch log events found for request ID {request_id} after multiple attempts.")
        print("This could be due to:")
        print("  - Log delay (try increasing wait time)")
        print("  - Incorrect log group/stream names")
        print("  - Request ID not appearing in logs")
        print("  - Insufficient permissions to read CloudWatch logs")
        if log_events:
            print(f"  - Found {len(log_events)} general log events, but none matched the request ID")
        return
    
    # Use the matching events for further processing
    log_events = matching_events
    
    print(f"Found {len(log_events)} log events:")
    
    # Look for the specific "Agent invoked" message with matching session ID
    agent_invoked_event = None
    for event in log_events:
        message_content = event.get('message', '')
        
        # Check if this is a JSON message
        if message_content.startswith('{'):
            try:
                log_data = json.loads(message_content)
                inner_message = log_data.get('message', '')
                session_id_from_log = log_data.get('sessionId', '')
                
                # Check if this is the "Agent invoked" message
                # We'll match on either session ID or request ID
                has_agent_invoked = "Agent invoked" in inner_message
                session_matches = session_id_from_log == session_id
                request_matches = f"Request ID: {request_id}" in inner_message
                
                if has_agent_invoked and (session_matches or request_matches):
                    agent_invoked_event = event
                    print(f"  Found matching agent invoked event:")
                    print(f"    Session ID match: {session_matches}")
                    print(f"    Request ID match: {request_matches}")
                    print(f"    Session ID from log: {session_id_from_log}")
                    print(f"    Expected session ID: {session_id}")
                    break
            except Exception as e:
                # If we can't parse as JSON, check the raw message
                if ("Agent invoked" in message_content and 
                    (f"Session ID: {session_id}" in message_content or 
                     f"Request ID: {request_id}" in message_content)):
                    agent_invoked_event = event
                    print(f"  Found matching agent invoked event in raw message")
        else:
            # Check raw message
            if ("Agent invoked" in message_content and 
                (f"Session ID: {session_id}" in message_content or 
                 f"Request ID: {request_id}" in message_content)):
                agent_invoked_event = event
                print(f"  Found matching agent invoked event in raw message")
    
    if agent_invoked_event:
        print("\n--- Found Agent Invoked Event ---")
        message_content = agent_invoked_event.get('message', '')
        print(f"  Raw Message: {message_content}")
        
        # Parse the timestamp from the message
        try:
            # Handle JSON formatted messages
            if message_content.startswith('{'):
                log_data = json.loads(message_content)
                inner_message = log_data.get('message', '')
            else:
                inner_message = message_content
            
            # Extract timestamp after "Start time:"
            if "Start time:" in inner_message:
                start_time_str = inner_message.split("Start time:")[1].strip()
                # Handle different timestamp formats
                if ',' in start_time_str:
                    # Format: "2026-02-11T19:44:38.558763, Request ID: ..."
                    start_time_str = start_time_str.split(',')[0].strip()
                
                # Parse the timestamp (2026-02-11T19:44:38.558763)
                # Handle microseconds and timezone
                if '.' in start_time_str and '+' not in start_time_str and 'Z' not in start_time_str:
                    # Add UTC timezone if missing
                    start_time_str += '+00:00'
                elif start_time_str.endswith('Z'):
                    # Replace Z with +00:00 for parsing
                    start_time_str = start_time_str[:-1] + '+00:00'
                
                start_time_dt = datetime.fromisoformat(start_time_str)
                # Convert to timestamp (seconds since epoch)
                start_time_timestamp = start_time_dt.timestamp()
                
                print(f"  Parsed Start Time: {start_time_str}")
                print(f"  Start Time Timestamp: {start_time_timestamp}")
                
                # Calculate latency difference
                difference = calculate_latency_difference(client_start_time, start_time_timestamp)
                print(f"  Difference from client start: {difference*1000:.2f}ms")
            else:
                print("  Could not find 'Start time:' in message")
        except Exception as e:
            print(f"  Error parsing timestamp: {e}")
            import traceback
            traceback.print_exc()
    else:
        print("\n--- No 'Agent invoked' event found with matching session ID ---")
    
    # Display all log events for reference
    print(f"\n--- All Matching Log Events ({len(log_events)} total) ---")
    for i, event in enumerate(log_events):
        timestamp = parse_cloudwatch_event_timestamp(event)
        event_time_iso = datetime.fromtimestamp(timestamp).isoformat() if timestamp else "Unknown"
        
        print(f"\n  Log Event {i+1}:")
        print(f"    CloudWatch Timestamp: {event_time_iso}")
        print(f"    Message: {event['message']}")
        
        if timestamp:
            difference = calculate_latency_difference(client_start_time, timestamp)
            print(f"    Difference from client start: {difference*1000:.2f}ms")
        
        # Try to parse the message as JSON to show more details
        try:
            message_content = event.get('message', '')
            if message_content.startswith('{'):
                log_data = json.loads(message_content)
                print(f"    Parsed Log Data:")
                for key, value in log_data.items():
                    print(f"      {key}: {value}")
        except:
            # If we can't parse as JSON, skip
            pass

if __name__ == '__main__':
    main()
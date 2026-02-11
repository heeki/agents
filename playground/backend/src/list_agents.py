#!/usr/bin/env python3
"""
Script to list all Bedrock agents in the account to help identify the correct agent ID.
"""

import boto3
import argparse

def list_agents(region='us-east-1'):
    """
    List all Bedrock agents in the account.
    """
    client = boto3.client('bedrock-agent', region_name=region)
    
    try:
        response = client.list_agents()
        
        print("Bedrock Agents in the account:")
        print("=" * 50)
        
        if 'agentSummaries' in response:
            for agent in response['agentSummaries']:
                print(f"Agent Name: {agent.get('agentName', 'N/A')}")
                print(f"Agent ID: {agent.get('agentId', 'N/A')}")
                print(f"Agent Status: {agent.get('agentStatus', 'N/A')}")
                print(f"Created: {agent.get('createdAt', 'N/A')}")
                print("-" * 30)
        else:
            print("No agents found.")
            
    except Exception as e:
        print(f"Error listing agents: {e}")

def list_agent_runtimes(region='us-east-1'):
    """
    List all Bedrock agent runtimes in the account.
    """
    client = boto3.client('bedrock-agentcore', region_name=region)
    
    try:
        response = client.list_runtimes()
        
        print("\nBedrock Agent Runtimes in the account:")
        print("=" * 50)
        
        if 'runtimeSummaries' in response:
            for runtime in response['runtimeSummaries']:
                print(f"Runtime Name: {runtime.get('runtimeName', 'N/A')}")
                print(f"Runtime ID: {runtime.get('runtimeId', 'N/A')}")
                print(f"Runtime ARN: {runtime.get('runtimeArn', 'N/A')}")
                print(f"Status: {runtime.get('status', 'N/A')}")
                print("-" * 30)
        else:
            print("No runtimes found.")
            
    except Exception as e:
        print(f"Error listing runtimes: {e}")

def main():
    parser = argparse.ArgumentParser(description='List Bedrock agents and runtimes')
    parser.add_argument('--region', default='us-east-1', help='AWS region')
    
    args = parser.parse_args()
    
    list_agents(args.region)
    list_agent_runtimes(args.region)

if __name__ == '__main__':
    main()
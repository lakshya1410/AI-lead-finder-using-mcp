"""
Test script to verify MCP connection and tools
Run this to diagnose issues with Bright Data MCP integration
"""
import asyncio
import os
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from langchain_mcp_adapters.client import MultiServerMCPClient
from dotenv import load_dotenv

load_dotenv()

async def test_mcp_connection():
    """Test MCP connection and available tools"""
    
    print("=" * 60)
    print("🧪 MCP Connection Test")
    print("=" * 60)
    
    # Step 1: Check environment variables
    print("\n1️⃣  Checking environment variables...")
    bright_data_token = os.getenv('BRIGHT_DATA_API_TOKEN')
    openai_key = os.getenv('OPENAI_API_KEY')
    
    if not bright_data_token:
        print("❌ BRIGHT_DATA_API_TOKEN not found!")
        print("   Add it to your .env file")
        return False
    else:
        print(f"✅ BRIGHT_DATA_API_TOKEN found: {bright_data_token[:10]}...")
    
    if not openai_key:
        print("❌ OPENAI_API_KEY not found!")
        print("   Add it to your .env file")
        return False
    else:
        print(f"✅ OPENAI_API_KEY found: {openai_key[:10]}...")
    
    # Step 2: Initialize MCP client
    print("\n2️⃣  Initializing MCP client...")
    try:
        client = MultiServerMCPClient({
            "bright_data": {
                "url": f"https://mcp.brightdata.com/sse?token={bright_data_token}",
                "transport": "sse",
            }
        })
        print("✅ MCP client created")
    except Exception as e:
        print(f"❌ Failed to create MCP client: {e}")
        return False
    
    # Step 3: Get available tools
    print("\n3️⃣  Fetching available tools...")
    try:
        tools = await client.get_tools()
        print(f"✅ Found {len(tools)} tools:")
        for i, tool in enumerate(tools, 1):
            print(f"   {i}. {tool.name}")
    except Exception as e:
        print(f"❌ Failed to get tools: {e}")
        return False
    
    # Step 4: Initialize OpenAI
    print("\n4️⃣  Initializing OpenAI...")
    try:
        llm = ChatOpenAI(
            openai_api_key=openai_key,
            model_name="gpt-4o-mini",
            temperature=0.3
        )
        print("✅ OpenAI client initialized")
    except Exception as e:
        print(f"❌ Failed to initialize OpenAI: {e}")
        return False
    
    # Step 5: Create agent
    print("\n5️⃣  Creating ReAct agent...")
    try:
        agent = create_react_agent(
            model=llm,
            tools=tools,
            prompt="You are a helpful web search assistant."
        )
        print("✅ Agent created successfully")
    except Exception as e:
        print(f"❌ Failed to create agent: {e}")
        return False
    
    # Step 6: Test simple search
    print("\n6️⃣  Testing simple web search...")
    try:
        result = await agent.ainvoke({
            "messages": [("human", "Search for 'OpenAI latest news' and summarize the top result")]
        })
        
        response = result["messages"][-1].content
        print("✅ Search successful!")
        print(f"\n📝 Response preview:\n{response[:300]}...")
        
    except Exception as e:
        print(f"❌ Search failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print("\n" + "=" * 60)
    print("✅ All tests passed! MCP is working correctly.")
    print("=" * 60)
    return True

async def test_lead_search():
    """Test actual lead search functionality"""
    
    print("\n\n" + "=" * 60)
    print("🧪 Lead Search Test")
    print("=" * 60)
    
    bright_data_token = os.getenv('BRIGHT_DATA_API_TOKEN')
    openai_key = os.getenv('OPENAI_API_KEY')
    
    if not bright_data_token or not openai_key:
        print("❌ Missing API keys")
        return False
    
    print("\n📋 Testing lead search with sample ICP...")
    
    try:
        client = MultiServerMCPClient({
            "bright_data": {
                "url": f"https://mcp.brightdata.com/sse?token={bright_data_token}",
                "transport": "sse",
            }
        })
        
        tools = await client.get_tools()
        
        llm = ChatOpenAI(
            openai_api_key=openai_key,
            model_name="gpt-4o-mini",
            temperature=0.3
        )
        
        agent = create_react_agent(
            model=llm,
            tools=tools,
            prompt="""You are a B2B lead finder. Search for real companies and decision-makers.
Return results as JSON array with fields: lead_name, designation, company_name, email, etc."""
        )
        
        # Test query
        query = """Find 2 leads for:
- Industry: Technology
- Job Title: CTO or VP Engineering
- Location: United States
- Company Size: 100-500 employees

Return JSON with: lead_name, designation, company_name, email, phone, linkedin, company_industry, company_size, company_location"""
        
        print("🔍 Searching...")
        result = await agent.ainvoke({
            "messages": [("human", query)]
        })
        
        response = result["messages"][-1].content
        print("\n📝 Lead Search Response:")
        print(response[:500])
        
        print("\n✅ Lead search test completed!")
        
    except Exception as e:
        print(f"❌ Lead search failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

if __name__ == "__main__":
    print("\n🚀 Starting MCP Diagnostic Tests\n")
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    # Run connection test
    success = loop.run_until_complete(test_mcp_connection())
    
    if success:
        # Run lead search test
        loop.run_until_complete(test_lead_search())
    
    loop.close()
    
    print("\n✅ Diagnostic complete!")
    print("\nIf all tests passed, run: python app.py")
    print("If tests failed, check your .env file and API keys")
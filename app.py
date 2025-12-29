import asyncio
import json
import os
import re
import aiohttp
from flask import Flask, request, jsonify, send_from_directory
import webbrowser
import threading
from flask_cors import CORS
from openai import OpenAI
from dotenv import load_dotenv
from datetime import datetime
from typing import Optional, List, Dict, Any

load_dotenv()

app = Flask(__name__, static_folder='static')
CORS(app)

# Global variables
mcp_client = None
openai_client = None

# Configuration
BRIGHT_DATA_API_TOKEN = os.getenv('BRIGHT_DATA_API_TOKEN', '')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')

# Initialize OpenAI client
if OPENAI_API_KEY:
    openai_client = OpenAI(api_key=OPENAI_API_KEY)

class BrightDataMCP:
    """Client for Bright Data MCP server with proper session management"""
    
    def __init__(self, api_token: str):
        self.api_token = api_token
        self.base_url = "https://mcp.brightdata.com"
        self.session_id: Optional[str] = None
        self.request_id = 0
        self._http_session: Optional[aiohttp.ClientSession] = None
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session"""
        if self._http_session is None or self._http_session.closed:
            self._http_session = aiohttp.ClientSession()
        return self._http_session
    
    async def close(self):
        """Close HTTP session"""
        if self._http_session and not self._http_session.closed:
            await self._http_session.close()
    
    def _next_id(self) -> int:
        """Get next request ID"""
        self.request_id += 1
        return self.request_id
    
    async def initialize(self, timeout: int = 30) -> bool:
        """Initialize MCP session - required before making tool calls"""
        url = f"{self.base_url}/mcp?token={self.api_token}"
        
        payload = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {
                    "name": "prospecting_pro",
                    "version": "1.0.0"
                }
            }
        }
        
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream"
        }
        
        try:
            session = await self._get_session()
            async with session.post(
                url,
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=timeout)
            ) as response:
                self.session_id = response.headers.get('Mcp-Session-Id')
                content_type = response.headers.get('Content-Type', '')
                
                if response.status == 200:
                    if 'text/event-stream' in content_type:
                        result = await self._parse_sse_response(response)
                    else:
                        result = await response.json()
                    
                    print(f"✅ MCP Initialize successful")
                    if self.session_id:
                        print(f"   Session ID: {self.session_id[:20]}...")
                    
                    await self._send_initialized()
                    return True
                else:
                    error_text = await response.text()
                    print(f"❌ MCP Initialize failed ({response.status}): {error_text[:300]}")
                    return False
                    
        except Exception as e:
            print(f"❌ MCP Initialize error: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    async def _send_initialized(self):
        """Send 'initialized' notification after successful init"""
        url = f"{self.base_url}/mcp?token={self.api_token}"
        
        payload = {
            "jsonrpc": "2.0",
            "method": "notifications/initialized"
        }
        
        headers = {"Content-Type": "application/json"}
        if self.session_id:
            headers["Mcp-Session-Id"] = self.session_id
        
        try:
            session = await self._get_session()
            async with session.post(url, json=payload, headers=headers) as response:
                pass
        except:
            pass
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any], timeout: int = 60) -> Dict:
        """Call a Bright Data MCP tool via JSON-RPC"""
        if not self.session_id:
            if not await self.initialize():
                return {"error": "Failed to initialize MCP session"}
        
        url = f"{self.base_url}/mcp?token={self.api_token}"
        
        payload = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments
            }
        }
        
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream"
        }
        if self.session_id:
            headers["Mcp-Session-Id"] = self.session_id
        
        try:
            session = await self._get_session()
            async with session.post(
                url,
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=timeout)
            ) as response:
                content_type = response.headers.get('Content-Type', '')
                
                if response.status == 200:
                    if 'text/event-stream' in content_type:
                        return await self._parse_sse_response(response)
                    else:
                        result = await response.json()
                        return result
                else:
                    error_text = await response.text()
                    print(f"❌ MCP Error ({response.status}): {error_text[:500]}")
                    
                    if response.status == 404 or "session" in error_text.lower():
                        self.session_id = None
                        print("   Attempting to re-initialize session...")
                        if await self.initialize():
                            return await self.call_tool(tool_name, arguments, timeout)
                    
                    return {"error": error_text, "status": response.status}
                    
        except asyncio.TimeoutError:
            print(f"❌ MCP call timed out after {timeout}s")
            return {"error": "timeout"}
        except Exception as e:
            print(f"❌ MCP call failed: {str(e)}")
            return {"error": str(e)}
    
    async def _parse_sse_response(self, response) -> Dict:
        """Parse Server-Sent Events response"""
        result = {}
        async for line in response.content:
            line = line.decode('utf-8').strip()
            if line.startswith('data:'):
                data = line[5:].strip()
                if data:
                    try:
                        parsed = json.loads(data)
                        if "result" in parsed or "error" in parsed:
                            return parsed
                    except json.JSONDecodeError:
                        continue
        return result
    
    async def search_web(self, query: str, count: int = 10) -> List[Dict]:
        """Search the web using Bright Data's search_engine tool"""
        print(f"🔍 Searching: {query}")
        
        result = await self.call_tool(
            tool_name="search_engine",
            arguments={
                "query": query,
                "count": count
            }
        )
        
        if "error" in result:
            print(f"❌ Search failed: {result.get('error', 'Unknown error')[:200]}")
            return []
        
        try:
            if "result" in result:
                content = result["result"]
                if isinstance(content, dict) and "content" in content:
                    for block in content.get("content", []):
                        if block.get("type") == "text":
                            text = block.get("text", "")
                            try:
                                parsed = json.loads(text)
                                if isinstance(parsed, list):
                                    return parsed
                                return [parsed]
                            except:
                                return [{"raw_text": text}]
                return [content] if content else []
            return []
        except Exception as e:
            print(f"❌ Error parsing search results: {e}")
            return []
    
    async def scrape_url(self, url: str) -> str:
        """Scrape a URL using Bright Data's scrape_as_markdown tool"""
        print(f"📄 Scraping: {url}")
        
        result = await self.call_tool(
            tool_name="scrape_as_markdown",
            arguments={"url": url}
        )
        
        if "error" in result:
            print(f"❌ Scrape failed: {result.get('error', 'Unknown error')[:200]}")
            return ""
        
        try:
            if "result" in result:
                content = result["result"]
                if isinstance(content, dict) and "content" in content:
                    for block in content.get("content", []):
                        if block.get("type") == "text":
                            return block.get("text", "")
                return str(content) if content else ""
            return ""
        except Exception as e:
            print(f"❌ Error parsing scrape results: {e}")
            return ""

def generate_email_patterns(name: str, company_domain: str) -> List[str]:
    """Generate possible email patterns from name and company domain"""
    if not name or not company_domain or name == 'N/A':
        return []
    
    # Clean the name
    name = name.strip().lower()
    name_parts = name.split()
    
    if len(name_parts) < 2:
        return []
    
    first = name_parts[0]
    last = name_parts[-1]
    
    # Remove common domain prefixes
    domain = company_domain.replace('www.', '').replace('http://', '').replace('https://', '').split('/')[0]
    
    patterns = [
        f"{first}.{last}@{domain}",
        f"{first}{last}@{domain}",
        f"{first}@{domain}",
        f"{first[0]}{last}@{domain}",
        f"{first}_{last}@{domain}",
        f"{last}.{first}@{domain}",
        f"{first[0]}.{last}@{domain}",
    ]
    
    return patterns


def extract_domain_from_url(url: str) -> str:
    """Extract domain from URL"""
    if not url:
        return ''
    
    # Remove protocol
    url = url.replace('https://', '').replace('http://', '').replace('www.', '')
    # Get domain
    domain = url.split('/')[0].split('?')[0]
    return domain


def build_search_queries(icp_data: Dict) -> List[str]:
    """Build effective search queries from ICP data"""
    queries = []
    
    industry = icp_data.get('industry', '')
    job_titles = icp_data.get('target_job_title', '').split(',')
    regions = icp_data.get('geographic_region', '').split(',')
    company_size = icp_data.get('company_size', '')
    technologies = icp_data.get('technology_used', '')
    
    # Get first title and region for focused queries
    primary_title = job_titles[0].strip() if job_titles else 'CEO'
    primary_region = regions[0].strip() if regions else ''
    
    # Query 1: LinkedIn profile search
    if primary_title and industry and primary_region:
        queries.append(f'site:linkedin.com/in "{primary_title}" "{industry}" {primary_region}')
    
    # Query 2: Company directory with contact info
    if industry and primary_region:
        queries.append(f'"{industry}" companies {primary_region} contact email phone address')
    
    # Query 3: Decision maker with email pattern
    if primary_title and industry:
        queries.append(f'{primary_title} {industry} email "@" {primary_region}')
    
    # Query 4: Company website and about page
    if industry and company_size:
        queries.append(f'{company_size} {industry} companies {primary_region} site:about OR site:contact')
    
    # Query 5: Technology stack and team
    if technologies and industry:
        queries.append(f'{industry} companies using {technologies.split(",")[0].strip()} team contact')
    
    # Query 6: Professional directory
    if primary_title and industry:
        queries.append(f'"{primary_title}" "{industry}" {primary_region} site:crunchbase.com OR site:zoominfo.com')
    
    # Query 7: News and press releases for recent hires
    if primary_title and industry:
        queries.append(f'"{primary_title}" joins OR appointed {industry} company {primary_region}')
    
    return queries[:8]  # Return up to 8 targeted queries


def calculate_confidence_score(lead_data: Dict, icp_criteria: Dict) -> Dict:
    """Calculate how well a lead matches the ICP"""
    matches = []
    score = 0
    
    # Industry match (30 points)
    lead_industry = str(lead_data.get('company_industry', '')).lower()
    target_industry = str(icp_criteria.get('industry', '')).lower()
    if lead_industry and target_industry and target_industry in lead_industry:
        score += 30
        matches.append("Industry match")
    
    # Job title match (25 points)
    lead_title = str(lead_data.get('designation', '')).lower()
    target_titles = str(icp_criteria.get('target_job_title', '')).lower().split(',')
    for title in target_titles:
        if title.strip() in lead_title or lead_title in title.strip():
            score += 25
            matches.append("Job title match")
            break
    
    # Location match (15 points)
    lead_location = str(lead_data.get('company_location', '')).lower()
    target_regions = str(icp_criteria.get('geographic_region', '')).lower().split(',')
    for region in target_regions:
        if region.strip() in lead_location:
            score += 15
            matches.append("Location match")
            break
    
    # Contact info available (20 points)
    if lead_data.get('email'):
        score += 10
        matches.append("Email available")
    if lead_data.get('linkedin'):
        score += 10
        matches.append("LinkedIn available")
    
    # Company size match (10 points)
    lead_size = str(lead_data.get('company_size', '')).lower()
    target_size = str(icp_criteria.get('company_size', '')).lower()
    if lead_size and target_size and (target_size in lead_size or lead_size in target_size):
        score += 10
        matches.append("Company size match")
    
    # Determine grade
    if score >= 80:
        grade = 'A'
    elif score >= 60:
        grade = 'B'
    elif score >= 40:
        grade = 'C'
    else:
        grade = 'D'
    
    return {
        'percentage': min(score, 100),
        'grade': grade,
        'matches': matches
    }

async def search_leads_with_mcp(icp_data: Dict) -> List[Dict]:
    """Search for leads using Bright Data MCP"""
    global mcp_client
    
    # Create new client for each search to avoid session issues
    if not BRIGHT_DATA_API_TOKEN:
        print("❌ BRIGHT_DATA_API_TOKEN not configured")
        return []
    
    # Always create a fresh client
    mcp_client = BrightDataMCP(BRIGHT_DATA_API_TOKEN)
    
    all_results = []
    queries = build_search_queries(icp_data)
    
    print(f"\n🔍 Executing {len(queries)} search queries...")
    
    for query in queries:
        results = await mcp_client.search_web(query, count=15)  # Increased to 15 for more results
        if results:
            all_results.extend(results)
            print(f"  ✅ Found {len(results)} results for: {query[:50]}...")
        else:
            print(f"  ⚠️ No results for: {query[:50]}...")
        
        # Small delay between queries to avoid rate limiting
        await asyncio.sleep(0.5)
    
    return all_results


def parse_search_results_with_ai(search_results: List[Dict], icp_data: Dict) -> List[Dict]:
    """Use OpenAI to parse search results into structured lead data"""
    if not openai_client:
        print("❌ OpenAI client not available")
        return []
    
    if not search_results:
        print("⚠️ No search results to parse")
        return []
    
    # Prepare the search results text - increased limit for more detail
    results_text = json.dumps(search_results, indent=2)[:30000]  # Increased to 30k chars for comprehensive extraction
    
    prompt = f"""You are an expert B2B lead intelligence analyst extracting REAL, VERIFIABLE data from web search results.

🎯 TARGET PROFILE:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• Industry: {icp_data.get('industry', 'N/A')}
• Job Titles: {icp_data.get('target_job_title', 'N/A')}
• Company Size: {icp_data.get('company_size', 'N/A')}
• Location: {icp_data.get('geographic_region', 'N/A')}
• Tech Stack: {icp_data.get('technology_used', 'N/A')}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📊 SEARCH RESULTS TO ANALYZE:
{results_text}

⚠️ ⚠️ MANDATORY EXTRACTION REQUIREMENTS:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. ✅ SOURCE URL: MUST include the complete URL where you found this person/company
2. ✅ LINKEDIN: Complete profile URL (https://linkedin.com/in/username)
3. ✅ EMAIL: Extract ANY email mentioned OR infer from patterns like:
   - firstname.lastname@company.com
   - contact@company.com
   - info@company.com
   - Look in page content, contact sections, author info
4. ✅ PHONE: Extract phone numbers in ANY format (+91-XXX, (555) XXX-XXXX, etc.)
5. ✅ COMPANY WEBSITE: Complete URL with https://
6. ✅ LOCATION: Full address if available, otherwise city, state, country
7. ✅ COMPANY INFO: Description, size, industry, founding year, revenue
8. ✅ TECHNOLOGY: Any tech stack mentioned (AWS, Python, React, etc.)
9. ✅ SOCIAL: Twitter, GitHub, Facebook profile URLs
10. ✅ VALIDATION: Every field must trace back to search results
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🔍 SMART EXTRACTION TIPS:
- Check URL slugs for names (linkedin.com/in/john-smith)
- Extract domain from website for email patterns
- Look for "Contact", "About", "Team" sections
- Find email formats mentioned in content
- Extract phone from contact sections
- Get company info from meta descriptions
- Find recent news, funding, hiring info

❌ NEVER FABRICATE - Only use explicit information from results

📤 OUTPUT FORMAT - Return ONLY this JSON array:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[
  {{
    "lead_name": "FirstName LastName",
    "designation": "Founder | CEO | CTO | VP Engineering | etc.",
    "company_name": "Company Name Inc.",
    
    "email": "person@company.com",
    "phone": "+91-9876543210 or +1-555-123-4567",
    "linkedin": "https://linkedin.com/in/username",
    "source_url": "https://exact-page-where-found.com",
    
    "company_website": "https://company.com",
    "company_about": "Detailed description of what the company does, their mission, products/services. Be comprehensive.",
    "company_industry": "SaaS | E-commerce | Fintech | Healthcare | Real Estate | etc.",
    "company_size": "1-10 | 11-50 | 51-200 | 201-500 | 500+ employees",
    "company_location": "City, State/Province, Country (Full address if available)",
    "company_email": "contact@company.com or info@company.com",
    "company_phone": "+91-XXX-XXX-XXXX",
    "company_address": "123 Street Name, Building, City, State, ZIP",
    "company_valuation": "$5M Series A | $50M valuation | Bootstrapped | etc.",
    "company_tech": "AWS, Python, React, PostgreSQL, Redis, etc.",
    "company_revenue": "$1M-$5M ARR | $10M+ | etc.",
    "company_founded": "2020 | 2018 | etc.",
    
    "social_profiles": {{
      "twitter": "https://twitter.com/username",
      "facebook": "https://facebook.com/company",
      "github": "https://github.com/username"
    }},
    
    "recent_news": "Raised $5M Series A from XYZ Ventures in Q4 2024 | Launched new product | Hired 20 engineers | etc.",
    "relevance_score": 8
  }}
]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🎯 EXTRACT 8-15 LEADS with maximum detail from the search results.
📋 Return ONLY valid JSON. No explanations, no markdown, just the array.
"""

    try:
        print("🤖 Parsing results with OpenAI...")
        
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are an expert B2B lead intelligence analyst. Extract MAXIMUM detail from search results. ALWAYS include source URLs, contact information, and company details. Use REAL data only - never fabricate. If you see a URL, email, phone, or any contact detail in the results, extract it. Look carefully at LinkedIn profiles, company pages, and contact sections."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.01,  # Extremely low for maximum accuracy
            max_tokens=8000  # Increased to 8000 for very detailed responses
        )
        
        response_text = response.choices[0].message.content.strip()
        
        # Extract JSON from response
        json_match = re.search(r'\[[\s\S]*\]', response_text)
        if json_match:
            leads_data = json.loads(json_match.group(0))
            print(f"✅ AI extracted {len(leads_data)} leads with detailed information")
            return leads_data
        else:
            print("⚠️ No valid JSON in AI response")
            return []
            
    except json.JSONDecodeError as e:
        print(f"❌ JSON parse error: {e}")
        print(f"Response preview: {response_text[:500] if 'response_text' in locals() else 'N/A'}")
        return []
    except Exception as e:
        print(f"❌ OpenAI error: {e}")
        import traceback
        traceback.print_exc()
        return []


async def search_leads(icp_data: Dict) -> List[Dict]:
    """Main function to search for leads using MCP + OpenAI"""
    print("\n" + "=" * 60)
    print(f"🚀 Starting Lead Search for: {icp_data.get('icp_name', 'Unknown ICP')}")
    print("=" * 60)
    
    # Step 1: Search using Bright Data MCP
    search_results = await search_leads_with_mcp(icp_data)
    
    if not search_results:
        print("❌ No search results from MCP")
        return []
    
    print(f"\n📊 Total raw results: {len(search_results)}")
    
    # Step 2: Parse results with OpenAI
    parsed_leads = parse_search_results_with_ai(search_results, icp_data)
    
    if not parsed_leads:
        print("❌ No leads extracted from search results")
        return []
    
    # Step 3: Structure and score leads
    structured_leads = []
    for lead_data in parsed_leads:
        structured = structure_lead_data(lead_data, icp_data)
        structured_leads.append(structured)
    
    # Sort by confidence score
    structured_leads.sort(
        key=lambda x: x['ai_analysis']['confidence_score'],
        reverse=True
    )
    
    print(f"\n✅ Final leads found: {len(structured_leads)}")
    return structured_leads

def structure_lead_data(lead_data: Dict, icp_data: Dict) -> Dict:
    """Structure lead data with confidence scoring and comprehensive information"""
    confidence = calculate_confidence_score(lead_data, icp_data)
    
    # Get social profiles
    social_profiles = lead_data.get('social_profiles', {})
    if isinstance(social_profiles, str):
        social_profiles = {}
    
    # Enrich email if not found
    email = lead_data.get('email', '')
    email_patterns = []
    
    if not email or email in ['Not found', 'N/A', '']:
        # Generate email patterns
        name = lead_data.get('lead_name', '')
        website = lead_data.get('company_website', '')
        
        if name and website and name not in ['N/A', 'Not found']:
            domain = extract_domain_from_url(website)
            if domain:
                email_patterns = generate_email_patterns(name, domain)
                if email_patterns:
                    email = email_patterns[0]  # Use first pattern as primary
    
    lead = {
        'lead': {
            'name': lead_data.get('lead_name', 'N/A'),
            'designation': lead_data.get('designation', 'N/A'),
            'company_name': lead_data.get('company_name', 'N/A'),
            'source': lead_data.get('source_url') or lead_data.get('source', 'Web Search'),
            'source_url': lead_data.get('source_url', ''),
            'contact_details': {
                'email': email or 'Not found',
                'email_patterns': email_patterns[:3] if email_patterns else [],
                'email_source': lead_data.get('source_url') or 'Generated Pattern',
                'phone': lead_data.get('phone') or 'Not found',
                'linkedin': lead_data.get('linkedin') or 'Not found'
            },
            'social_profiles': {
                'twitter': social_profiles.get('twitter', ''),
                'facebook': social_profiles.get('facebook', ''),
                'github': social_profiles.get('github', '')
            }
        },
        'company': {
            'name': lead_data.get('company_name', 'N/A'),
            'about': lead_data.get('company_about', 'N/A'),
            'industry': lead_data.get('company_industry', 'N/A'),
            'size': lead_data.get('company_size', 'N/A'),
            'location': lead_data.get('company_location', 'N/A'),
            'website': lead_data.get('company_website', 'N/A'),
            'contact_info': {
                'email': lead_data.get('company_email') or 'Not found',
                'phone': lead_data.get('company_phone') or 'Not found'
            },
            'address': lead_data.get('company_address') or 'Not found',
            'valuation': lead_data.get('company_valuation') or 'Not found',
            'tech_stack': lead_data.get('company_tech') or 'Not found',
            'revenue': lead_data.get('company_revenue', ''),
            'founded': lead_data.get('company_founded', ''),
            'recent_news': lead_data.get('recent_news', ''),
            'source_urls': {
                'profile': lead_data.get('source_url', ''),
                'website': lead_data.get('company_website', ''),
                'linkedin': lead_data.get('linkedin', '')
            }
        },
        'ai_analysis': {
            'confidence_score': confidence['percentage'],
            'grade': confidence['grade'],
            'matching_criteria': confidence['matches'],
            'insights': generate_insights(lead_data, confidence),
            'recommendation': generate_recommendation(confidence['percentage']),
            'relevance_score': lead_data.get('relevance_score', 5)
        },
        'metadata': {
            'source_url': lead_data.get('source_url', ''),
            'extraction_timestamp': datetime.now().isoformat(),
            'data_completeness': calculate_data_completeness(lead_data),
            'email_generated': bool(email_patterns),
            'contact_quality': 'High' if (email and email != 'Not found') or (lead_data.get('phone') and lead_data.get('phone') != 'Not found') else 'Low'
        }
    }
    
    return lead


def calculate_data_completeness(lead_data: Dict) -> Dict:
    """Calculate how complete the lead data is"""
    total_fields = 0
    filled_fields = 0
    
    key_fields = [
        'lead_name', 'designation', 'company_name', 'email', 'phone', 
        'linkedin', 'company_about', 'company_website', 'company_location',
        'company_size', 'company_industry'
    ]
    
    for field in key_fields:
        total_fields += 1
        value = lead_data.get(field, '')
        if value and value not in ['N/A', 'Not found', '', 'Unknown']:
            filled_fields += 1
    
    percentage = int((filled_fields / total_fields) * 100) if total_fields > 0 else 0
    
    return {
        'percentage': percentage,
        'filled_fields': filled_fields,
        'total_fields': total_fields,
        'status': 'Complete' if percentage >= 80 else 'Partial' if percentage >= 50 else 'Limited'
    }

def generate_insights(lead_data: Dict, confidence: Dict) -> List[str]:
    """Generate AI insights about the lead"""
    insights = []
    
    if confidence['percentage'] >= 80:
        insights.append("🎯 Excellent match! This lead closely aligns with your ICP.")
    elif confidence['percentage'] >= 60:
        insights.append("✅ Good match with most key criteria met.")
    elif confidence['percentage'] >= 40:
        insights.append("⚠️ Partial match - review carefully before outreach.")
    else:
        insights.append("📋 Low match - may need additional qualification.")
    
    if 'Industry match' in confidence['matches']:
        insights.append(f"🏢 Industry alignment: {lead_data.get('company_industry', 'N/A')}")
    
    if 'Job title match' in confidence['matches']:
        insights.append(f"👤 Decision-maker: {lead_data.get('designation', 'N/A')}")
    
    if 'Email available' in confidence['matches']:
        insights.append("✉️ Direct contact information available")
    
    if 'LinkedIn available' in confidence['matches']:
        insights.append("💼 LinkedIn profile available for outreach")
    
    return insights

def generate_recommendation(score):
    """Generate action recommendation"""
    if score >= 80:
        return "PRIORITY: High-value lead - initiate outreach immediately"
    elif score >= 60:
        return "QUALIFIED: Good fit - add to outreach campaign"
    elif score >= 40:
        return "NURTURE: Potential fit - add to nurture sequence"
    else:
        return "RESEARCH: Requires additional qualification"

@app.route('/api/search-leads', methods=['POST'])
def search_leads_endpoint():
    """Endpoint to search for leads"""
    try:
        print("\n" + "="*60)
        print("🔔 RECEIVED /api/search-leads REQUEST")
        print("="*60)
        
        icp_data = request.json
        print(f"📋 Request data: {json.dumps(icp_data, indent=2)}")
        print(f"\n📋 ICP Name: {icp_data.get('icp_name', 'N/A')}")
        
        # Validate required fields
        required_fields = ['icp_name', 'company_size', 'industry', 'target_job_title', 
                          'geographic_region', 'technology_used', 'pain_points', 
                          'min_budget', 'max_budget']
        
        missing_fields = [field for field in required_fields if field not in icp_data]
        if missing_fields:
            error_msg = f'Missing required fields: {", ".join(missing_fields)}'
            print(f"❌ Validation Error: {error_msg}")
            return jsonify({'error': error_msg}), 400
        
        print("✅ All required fields present")
        print("🚀 Starting lead search...")
        
        # Run async search with proper loop management
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            leads = loop.run_until_complete(search_leads(icp_data))
        finally:
            # Clean up resources
            if mcp_client:
                try:
                    loop.run_until_complete(mcp_client.close())
                except:
                    pass
            loop.close()
        
        print(f"\n✅ Search completed! Returning {len(leads)} leads to frontend")
        print("="*60 + "\n")
        
        return jsonify({
            'success': True,
            'icp_name': icp_data['icp_name'],
            'timestamp': datetime.now().isoformat(),
            'total_leads': len(leads),
            'leads': leads
        })
    
    except Exception as e:
        print(f"\n❌ API Error: {str(e)}")
        import traceback
        traceback.print_exc()
        print("="*60 + "\n")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'mcp_client_initialized': mcp_client is not None,
        'openai_client_ready': openai_client is not None,
        'bright_data_configured': bool(BRIGHT_DATA_API_TOKEN),
        'openai_configured': bool(OPENAI_API_KEY)
    })


@app.route('/')
def serve_index():
    """Serve the frontend index.html from the static folder"""
    return send_from_directory('static', 'index.html')

if __name__ == '__main__':
    print("=" * 60)
    print("🚀 Lead Generation Server with OpenAI + Bright Data MCP")
    print("=" * 60)
    
    # Check configuration
    print("\n🔧 Configuration Check:")
    print(f"  BRIGHT_DATA_API_TOKEN: {'✅ Set' if BRIGHT_DATA_API_TOKEN else '❌ Not set'}")
    print(f"  OPENAI_API_KEY: {'✅ Set' if OPENAI_API_KEY else '❌ Not set'}")
    print(f"  OpenAI Client: {'✅ Ready' if openai_client else '❌ Not initialized'}")
    
    if not BRIGHT_DATA_API_TOKEN or not OPENAI_API_KEY:
        print("\n⚠️  WARNING: Required API tokens not configured!")
        print("Please set BRIGHT_DATA_API_TOKEN and OPENAI_API_KEY in your .env file.")
        print("The server will start but lead search will not work.\n")
    else:
        # Initialize MCP client (will be fully initialized on first use)
        mcp_client = BrightDataMCP(BRIGHT_DATA_API_TOKEN)
        print("\n✅ MCP Client ready!")
    
    print("\n✅ Server starting")
    print("📡 Backend: http://localhost:5000")
    print("🌐 Frontend: http://localhost:5000")
    print("=" * 60)
    
    # Auto-open browser
    def _open_browser():
        try:
            webbrowser.open('http://localhost:5000')
        except:
            pass
    
    threading.Timer(1.0, _open_browser).start()
    
    # Start Flask server
    app.run(debug=True, host='0.0.0.0', port=5000, use_reloader=False)
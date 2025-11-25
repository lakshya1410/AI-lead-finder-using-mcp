# 🎯 AI Lead Generation System

A complete B2B lead generation system powered by Bright Data's MCP server and OpenAI, designed to find and qualify leads matching your Ideal Customer Profile (ICP).

## 🌟 Features

- **Intelligent Lead Discovery**: AI-powered search across LinkedIn and web sources
- **ICP Matching**: Define detailed customer profiles with 8+ criteria
- **Confidence Scoring**: AI analyzes each lead and provides match percentage
- **Contact Extraction**: Automatically finds email, phone, LinkedIn profiles
- **Company Intelligence**: Comprehensive company data including valuation, tech stack
- **Visual Dashboard**: Beautiful interface with real-time results
- **AI Insights**: Actionable recommendations for each lead

## 📋 Prerequisites

1. **Bright Data Account**
   - Sign up at [Bright Data](https://brightdata.com)
   - Get your API token from [User Settings](https://brightdata.com/cp/setting/users)
   - Free tier includes 5,000 requests/month

2. **OpenAI API Key**
   - Get from [OpenAI Platform](https://platform.openai.com/api-keys)
   - Recommended model: GPT-4o (set in code)

3. **Python 3.8+**
   - Check: `python --version`

## 🚀 Quick Start

### Step 1: Clone/Download the Project

Create a project directory and save all the artifacts:
```bash
mkdir lead-generation-system
cd lead-generation-system
```

Save these files:
- `app.py` - Backend server
- `index.html` - Frontend interface
- `requirements.txt` - Python dependencies
- `.env.example` - Environment template

### Step 2: Install Dependencies

```bash
# Create virtual environment (recommended)
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate

# Install requirements
pip install -r requirements.txt
```

### Step 3: Configure Environment

```bash
# Copy example env file
cp .env.example .env

# Edit .env and add your keys
nano .env  # or use any text editor
```

Your `.env` should look like:
```env
BRIGHT_DATA_API_TOKEN=2dceb1aa0***************************
OPENAI_API_KEY=sk-proj-***************************
```

### Step 4: Start the Backend

```bash
python app.py
```

You should see:
```
Available tools: ['search_engine', 'scrape_as_markdown', 'web_data_linkedin_profile', ...]
MCP Agent initialized successfully!
Starting Lead Generation Server...
 * Running on http://0.0.0.0:5000
```

### Step 5: Open the Frontend

Simply open `index.html` in your browser, or serve it:

```bash
# Using Python's built-in server (in a new terminal)
python -m http.server 8000
```

Then visit: `http://localhost:8000`

## 📖 How to Use

### 1. Define Your ICP

Fill in the form with your target customer profile:

- **ICP Name**: e.g., "Enterprise SaaS Decision Makers"
- **Company Size**: Select from dropdown (1-10, 11-50, 51-200, etc.)
- **Industry**: e.g., "Technology, SaaS, Healthcare"
- **Target Job Title**: e.g., "CTO, VP Engineering, Head of IT"
- **Geographic Region**: e.g., "United States, Europe"
- **Technology Used**: e.g., "AWS, Salesforce, React, Python"
- **Pain Points**: Describe problems your solution solves
- **Budget Range**: Min and max budget in dollars

### 2. Search for Leads

Click "🔍 Search for Leads" and wait 30-60 seconds while AI:
- Searches across LinkedIn and web sources
- Identifies matching companies
- Finds key decision-makers
- Extracts contact information
- Analyzes ICP fit

### 3. Review Results

Each lead card shows:

**Lead Information**
- Name and job title
- Company affiliation
- Contact details (email, phone, LinkedIn)

**Company Details**
- Industry and size
- Location and website
- Company description
- Contact information

**AI Analysis**
- Confidence score (0-100%)
- Letter grade (A, B, C, D)
- Matching criteria
- AI insights
- Action recommendation

### 4. Export & Use

- Copy contact details for outreach
- Use AI recommendations to prioritize
- Export data (add export feature if needed)

## 🎨 Example ICP Configuration

```yaml
ICP Name: "Mid-Market SaaS Companies"
Company Size: "51-200 employees"
Industry: "Software, Technology, SaaS"
Target Job Title: "VP of Sales, CRO, Sales Director"
Geographic Region: "United States, Canada"
Technology Used: "Salesforce, HubSpot, Outreach"
Pain Points: "Need to improve sales productivity, struggling with lead qualification, looking for better sales analytics"
Budget Range: $50,000 - $500,000
```

## 🔧 Configuration Options

### Changing the AI Model

In `app.py`, modify:
```python
llm = ChatOpenAI(
    openai_api_key=os.getenv("OPENAI_API_KEY"),
    model_name="gpt-4o",  # Change to gpt-4-turbo, gpt-3.5-turbo, etc.
    temperature=0.2
)
```

### Adjusting Search Results

In `app.py`, change the number of leads:
```python
search_query = f"""
Find potential B2B leads matching this ICP:
...
1. Search for 5-10 companies matching this profile  # Change this number
```

### Customizing Confidence Scoring

Modify weights in the `calculate_confidence_score()` function:
```python
# Industry match (20 points)  # Adjust these weights
# Company size match (15 points)
# Job title match (25 points)
# etc.
```

## 🐛 Troubleshooting

### Backend won't start
```bash
# Check Python version
python --version  # Should be 3.8+

# Reinstall dependencies
pip install -r requirements.txt --force-reinstall

# Check environment variables
cat .env  # Verify tokens are present
```

### "MCP client initialization failed"
- Verify your Bright Data API token is correct
- Check you have available requests in your Bright Data account
- Ensure internet connection is stable

### "OpenAI API error"
- Verify your OpenAI API key is valid
- Check you have API credits
- Try using a different model (gpt-3.5-turbo is cheaper)

### No leads found
- Broaden your search criteria
- Check if your ICP is too specific
- Verify Bright Data service is working

### CORS errors in browser
- Ensure backend is running on port 5000
- Check `flask-cors` is installed
- Try accessing frontend via `http://localhost` not `file://`

## 📊 API Endpoints

### POST /api/search-leads
Search for leads matching ICP criteria

**Request Body:**
```json
{
  "icp_name": "Enterprise SaaS Buyers",
  "company_size": "501-1000",
  "industry": "Technology",
  "target_job_title": "CTO, VP Engineering",
  "geographic_region": "United States",
  "technology_used": "AWS, Kubernetes",
  "pain_points": "Need scalable infrastructure",
  "min_budget": "100000",
  "max_budget": "1000000"
}
```

**Response:**
```json
{
  "success": true,
  "icp_name": "Enterprise SaaS Buyers",
  "timestamp": "2024-01-15T10:30:00",
  "total_leads": 5,
  "leads": [...]
}
```

### GET /api/health
Check backend health status

**Response:**
```json
{
  "status": "healthy",
  "mcp_initialized": true
}
```

## 🚀 Production Deployment

### Using Gunicorn

```bash
pip install gunicorn

gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

### Using Docker

Create `Dockerfile`:
```dockerfile
FROM python:3.9-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["python", "app.py"]
```

Build and run:
```bash
docker build -t lead-gen-system .
docker run -p 5000:5000 --env-file .env lead-gen-system
```

### Environment Variables for Production

Add to your production environment:
```env
FLASK_ENV=production
SECRET_KEY=your_secret_key_here
BRIGHT_DATA_API_TOKEN=***
OPENAI_API_KEY=***
```

## 💡 Tips for Best Results

1. **Start Broad**: Begin with broader criteria, then narrow down
2. **Use Specific Keywords**: Include relevant technologies and pain points
3. **Combine Sources**: The AI searches multiple sources for better coverage
4. **Verify Contacts**: Always verify contact information before outreach
5. **Iterate**: Refine your ICP based on results quality
6. **Monitor Usage**: Keep track of Bright Data and OpenAI API usage

## 🔐 Security Best Practices

- Never commit `.env` file to version control
- Use environment variables for all sensitive data
- Implement rate limiting in production
- Add authentication for production deployments
- Validate all user inputs
- Use HTTPS in production

## 📈 Scaling Considerations

- Add Redis for caching search results
- Implement background job queue (Celery)
- Use database for storing leads (PostgreSQL)
- Add user authentication and multi-tenancy
- Implement export to CRM functionality
- Add webhook integrations

## 🤝 Contributing

This is an MVP - feel free to extend with:
- Database integration
- User authentication
- CRM integrations (Salesforce, HubSpot)
- Advanced filtering and sorting
- Lead scoring models
- Email verification services
- Bulk export (CSV, Excel)

## 📄 License

This is a demonstration project. Ensure compliance with:
- Bright Data Terms of Service
- OpenAI Terms of Service
- LinkedIn Terms of Service
- GDPR and data privacy regulations

## 🆘 Support

- **Bright Data Docs**: https://docs.brightdata.com
- **LangChain MCP**: https://python.langchain.com/docs/integrations/tools/mcp
- **OpenAI API**: https://platform.openai.com/docs

## 🎯 Roadmap

- [ ] Database integration for lead storage
- [ ] Email validation API integration
- [ ] CRM export functionality
- [ ] Advanced lead scoring
- [ ] Bulk search capabilities
- [ ] Email outreach templates
- [ ] Analytics dashboard
- [ ] API rate limiting

---

**Built with ❤️ using Bright Data MCP, LangChain, OpenAI, Flask, and modern web technologies**
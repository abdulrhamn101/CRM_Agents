import os
import csv
import json
# from dotenv import load_dotenv
from openai import OpenAI


# load_dotenv()

OPENAI_API_KEY = "OPENAI_API_KEY"#os.getenv("OPENAI_API_KEY")


class CampaignAgent:
    """
    Task 2: Campaign Agent

    Input:
    - saudi_companies_500.csv

    Process:
    - Reads company data.
    - Generates personalized campaign emails using OpenAI API.

    Output:
    - campaign_emails.csv
    """

    def __init__(self):
        if not OPENAI_API_KEY:
            raise ValueError("Missing OPENAI_API_KEY. Add it inside .env file.")

        self.client = OpenAI(api_key=OPENAI_API_KEY)

    def read_companies(self, input_file="saudi_companies_500.csv", limit=20):
        companies = []

        with open(input_file, mode="r", encoding="utf-8-sig") as file:
            reader = csv.DictReader(file)

            for row in reader:
                company_name = row.get("company_name", "").strip()

                if company_name:
                    companies.append(row)

                if limit and len(companies) >= limit:
                    break

        return companies

    def read_selected_companies(self, input_file, limit=None):
        with open(input_file, mode="r", encoding="utf-8") as file:
            records = json.load(file)

        if not isinstance(records, list):
            raise ValueError(
                f"{input_file} must contain a JSON list of company records."
            )

        companies = []
        for row in records:
            name = (row.get("company_name") or row.get("name") or "").strip()
            if not name:
                continue
            row["company_name"] = name
            companies.append(row)
            if limit and len(companies) >= limit:
                break

        return companies

    def ask_openai_json(self, prompt):
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                temperature=0.4,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a professional B2B sales campaign assistant. "
                            "Return valid JSON only. No markdown. No explanation."
                        )
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )

            text = response.choices[0].message.content.strip()
            text = text.replace("```json", "").replace("```", "").strip()

            return json.loads(text)

        except Exception:
            return {}

    def generate_email_for_company(self, company):
        company_name = company.get("company_name", "")
        arabic_name = company.get("arabic_name", "")
        sector = company.get("sector", "")
        sub_sector = company.get("sub_sector", "")
        city = company.get("city", "")
        country = company.get("country", "")
        website = company.get("website", "")
        email = company.get("email", "")
        phone = company.get("phone", "")
        linkedin_url = company.get("linkedin_url", "")
        employees = company.get("employees", "")
        founded_year = company.get("founded_year", "")
        description = company.get("description", "")
        is_startup = company.get("is_startup", "")
        is_listed = company.get("is_listed", "")
        tags = company.get("tags", "")

        prompt = f"""
Generate a personalized B2B cold email for this company.
<company>
Company data:
Company name: {company_name}
Arabic name: {arabic_name}
Sector: {sector}
Sub-sector: {sub_sector}
City: {city}
Country: {country}
Employees: {employees}
Founded year: {founded_year}
Website: {website}
Email: {email}
Phone: {phone}
LinkedIn: {linkedin_url}
Description: {description}
Is startup: {is_startup}
Is listed: {is_listed}
Tags: {tags}
</company>

<beamdata_services>
BeamData offers:
- AI automation
- Data analytics
</beamdata_services>

<rules>
- Make the email professional and short.
- Do not invent fake facts.
- Personalize using sector, sub-sector, description, and tags.
- Sender is BeamData Team.
- Goal is to schedule a short meeting.
- Return JSON only.

Return JSON in this exact format:
{{
  "email_subject": "subject here",
  "email_body": "email body here",
  "campaign_goal": "goal here",
  "suggested_service": "service here"
}}
</rules>"""

        data = self.ask_openai_json(prompt)

        if not data:
            return self.generate_fallback_email(company)

        return {
            "company_name": company_name,
            "arabic_name": arabic_name,
            "sector": sector,
            "sub_sector": sub_sector,
            "city": city,
            "country": country,
            "website": website,
            "email": email,
            "phone": phone,
            "linkedin_url": linkedin_url,
            "employees": employees,
            "founded_year": founded_year,
            "description": description,
            "tags": tags,
            "email_subject": data.get("email_subject", f"AI Automation Opportunity for {company_name}"),
            "email_body": data.get("email_body", ""),
            "campaign_goal": data.get("campaign_goal", "Schedule a short meeting"),
            "suggested_service": data.get("suggested_service", "AI automation and data analytics")
        }

    def generate_fallback_email(self, company):
        company_name = company.get("company_name", "")
        arabic_name = company.get("arabic_name", "")
        sector = company.get("sector", "")
        sub_sector = company.get("sub_sector", "")
        city = company.get("city", "")
        country = company.get("country", "")
        website = company.get("website", "")
        email = company.get("email", "")
        phone = company.get("phone", "")
        linkedin_url = company.get("linkedin_url", "")
        employees = company.get("employees", "")
        founded_year = company.get("founded_year", "")
        description = company.get("description", "")
        tags = company.get("tags", "")

        subject = f"AI Automation Opportunity for {company_name}"

        body = f"""
Dear {company_name} Team,

We noticed that your organization operates in the {sector} sector, specifically in {sub_sector}.

At BeamData, we provide AI automation and data-driven solutions that help organizations improve workflows, lead qualification, CRM automation, campaign automation, and proposal generation.

Based on your company profile and focus areas such as {tags}, we believe there may be an opportunity to support your digital and business goals.

We would be happy to schedule a short meeting to explore how our solution can help.

Best regards,
BeamData Team
"""

        return {
            "company_name": company_name,
            "arabic_name": arabic_name,
            "sector": sector,
            "sub_sector": sub_sector,
            "city": city,
            "country": country,
            "website": website,
            "email": email,
            "phone": phone,
            "linkedin_url": linkedin_url,
            "employees": employees,
            "founded_year": founded_year,
            "description": description,
            "tags": tags,
            "email_subject": subject,
            "email_body": body.strip(),
            "campaign_goal": "Schedule a short meeting",
            "suggested_service": "AI automation and data analytics"
        }

    def save_campaign_emails(self, emails, output_file="campaign_emails.csv"):
        with open(output_file, mode="w", newline="", encoding="utf-8-sig") as file:
            writer = csv.writer(file)

            writer.writerow([
                "company_name",
                "arabic_name",
                "sector",
                "sub_sector",
                "city",
                "country",
                "website",
                "email",
                "phone",
                "linkedin_url",
                "employees",
                "founded_year",
                "description",
                "tags",
                "email_subject",
                "email_body",
                "campaign_goal",
                "suggested_service"
            ])

            for email in emails:
                writer.writerow([
                    email["company_name"],
                    email["arabic_name"],
                    email["sector"],
                    email["sub_sector"],
                    email["city"],
                    email["country"],
                    email["website"],
                    email["email"],
                    email["phone"],
                    email["linkedin_url"],
                    email["employees"],
                    email["founded_year"],
                    email["description"],
                    email["tags"],
                    email["email_subject"],
                    email["email_body"],
                    email["campaign_goal"],
                    email["suggested_service"]
                ])

        return output_file

    def run(
        self,
        input_file="saudi_companies_500.csv",
        limit=20,
        source="csv",
        output_file="campaign_emails.csv",
        progress_callback=None,
    ):
        if source == "selected":
            companies = self.read_selected_companies(input_file=input_file, limit=limit)
        else:
            companies = self.read_companies(input_file=input_file, limit=limit)

        campaign_emails = []
        total = len(companies)

        for idx, company in enumerate(companies, start=1):
            email = self.generate_email_for_company(company)
            campaign_emails.append(email)
            if progress_callback is not None:
                progress_callback(idx, total, company.get("company_name", ""))

        saved_path = self.save_campaign_emails(campaign_emails, output_file=output_file)

        return {
            "total_companies": len(campaign_emails),
            "output_file": saved_path,
            "emails": campaign_emails,
        }
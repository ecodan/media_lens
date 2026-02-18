# Product Overview

## Mission Statement
Media Lens is a Python-based tool designed to systematically reveal media bias and differing worldviews through automated, comparative analysis of news headlines and content framing. By juxtaposing how different sources report on the same events, Media Lens empowers users to see beyond the surface narrative and understand the underlying editorial choices.

## Core Value Proposition
- **Transparency through Juxtaposition**: Automatically surfacing differences in coverage for the same day/week.
- **Automated Analysis**: Leveraging LLMs to perform sentiment and framing analysis at scale, a task that would be tedious for humans.
- **Historical Consistency**: Maintaining a rigorous week-over-week record using ISO standards, ensuring longitudinal studies are valid.

## Key Features
1. **Hybrid Temporal Analysis**:
    - **Current Events (Rolling 7-Day)**: Provides an always-fresh view of the last week for immediate relevance.
    - **Historical Tracking (ISO Weeks)**: Locks analysis into standard Monday-Sunday weeks for consistent historical records.
2. **Multi-Source Comparison**: Side-by-side visualization of headlines and extracted topics from configurable news sources.
3. **AI-Powered Insight**:
    - **Sentiment Analysis**: Quantifying the emotional tone of coverage.
    - **Framing Detection**: Identifying the specific angles and narratives used by each outlet.
    - **Summarization**: Distilling complex news cycles into digestible summaries.
4. **Static Report Generation**: Produces self-contained HTML reports with integrated **Reader View** pages for full-text article access.
5. **Universal Hosting**: Reports can be hosted on any static platform (e.g., S3, SFTP, GCS).

## Target Audience
- **Media Researchers**: For analyzing trends in bias and coverage over time.
- **Journalists**: For understanding how their peers are covering stories.
- **General Public**: For media literacy and escaping filter bubbles.

## User Persona
- **The Operator**: Technical user who runs the Python CLI, manages the configuration, and deploys the site.
- **The Reader**: Consumer of the generated HTML reports, looking for quick insights into media bias.

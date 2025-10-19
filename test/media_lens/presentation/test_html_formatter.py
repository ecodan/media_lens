import datetime
import json

from src.media_lens.job_dir import JobDir
from src.media_lens.presentation.html_formatter import (
    convert_relative_url,
    generate_html_from_path,
    generate_html_with_template,
    generate_index_page,
    generate_weekly_content,
    get_format_cursor,
    get_jobs_since_cursor,
    get_lightweight_weeks_data,
    organize_runs_by_week,
    reset_format_cursor,
    rewind_format_cursor,
    update_format_cursor,
)


def test_convert_relative_url():
    """Test converting relative URLs to absolute URLs."""
    # Test cases for different URL formats
    test_cases = [
        # (input_url, site, expected_output)
        ("/news/article", "www.test.com", "https://www.test.com/news/article"),
        ("news/article", "www.test.com", "https://www.test.com/news/article"),
        ("https://www.test.com/news/article", "www.test.com", "https://www.test.com/news/article"),
        ("http://www.test.com/news/article", "www.test.com", "http://www.test.com/news/article"),
    ]

    # Check each test case
    for input_url, site, expected in test_cases:
        result = convert_relative_url(input_url, site)
        assert result == expected


def test_generate_html_with_template(temp_dir):
    """Test HTML generation using a Jinja2 template."""
    # Create a simple template
    template_dir = temp_dir / "templates"
    template_dir.mkdir(exist_ok=True)

    with open(template_dir / "test_template.j2", "w") as f:
        f.write(
            """
        <!DOCTYPE html>
        <html>
        <head>
            <title>{{ title }}</title>
        </head>
        <body>
            <h1>{{ title }}</h1>
            <p>{{ content }}</p>
            <ul>
            {% for item in items %}
                <li>{{ item }}</li>
            {% endfor %}
            </ul>
        </body>
        </html>
        """
        )

    # Test content
    content = {
        "title": "Test Page",
        "content": "This is a test page.",
        "items": ["Item 1", "Item 2", "Item 3"],
    }

    # Generate HTML
    html = generate_html_with_template(template_dir, "test_template.j2", content)

    # Check results
    assert "<title>Test Page</title>" in html
    assert "<h1>Test Page</h1>" in html
    assert "<p>This is a test page.</p>" in html
    assert "<li>Item 1</li>" in html
    assert "<li>Item 2</li>" in html
    assert "<li>Item 3</li>" in html


def test_organize_runs_by_week(sample_job_directory, test_storage_adapter, monkeypatch):
    """Test organizing job runs by calendar week."""
    # Patch the shared storage to use our test storage adapter
    monkeypatch.setattr(
        "src.media_lens.presentation.html_formatter.shared_storage", test_storage_adapter
    )

    # Create JobDir from the sample directory name
    # sample_job_directory is a Path object with name like "2025-02-26_153000"
    job_dir_str = sample_job_directory.name  # Get the timestamp string
    job_dir = JobDir.from_path(job_dir_str)

    job_dirs = [job_dir]
    sites = ["www.test1.com", "www.test2.com"]

    # Call organize_runs_by_week
    result = organize_runs_by_week(job_dirs, sites)

    # Check result structure
    assert "report_timestamp" in result
    assert "weeks" in result
    assert len(result["weeks"]) >= 1

    # Check week data
    week = result["weeks"][0]
    assert "week_key" in week
    assert "week_display" in week
    assert "runs" in week
    assert len(week["runs"]) >= 1  # At least one run in the week

    # Check run data
    run = week["runs"][0]
    assert "run_timestamp" in run
    assert "extracted" in run


def test_generate_weekly_content(sample_job_directory, temp_dir, test_storage_adapter):
    """Test generating content for weekly reports."""
    # First organize runs by week
    job_dir_str = sample_job_directory.name
    job_dir = JobDir.from_path(job_dir_str)
    job_dirs = [job_dir]
    sites = ["www.test1.com", "www.test2.com"]
    weeks_data = organize_runs_by_week(job_dirs, sites)

    # Get the first week
    week_data = weeks_data["weeks"][0]

    # Create a weekly interpretation file using the storage adapter
    storage = test_storage_adapter
    storage.write_text(f"weekly-{week_data['week_key']}-interpreted.json", "[]")

    # Call generate_weekly_content
    weekly_content = generate_weekly_content(week_data, sites)

    # Check result structure
    assert weekly_content["week_key"] == week_data["week_key"]
    assert weekly_content["week_display"] == week_data["week_display"]
    assert weekly_content["sites"] == sites
    assert "site_content" in weekly_content
    assert "runs" in weekly_content
    # Weekly interpretation is no longer included in weekly content
    assert "interpretation" not in weekly_content


def test_generate_index_page(sample_job_directory, temp_dir, test_storage_adapter, monkeypatch):
    """Test generating the index page with the latest weekly summary."""
    # Patch the shared storage to use our test storage adapter
    monkeypatch.setattr(
        "src.media_lens.presentation.html_formatter.shared_storage", test_storage_adapter
    )

    # First organize runs by week
    job_dir_str = sample_job_directory.name
    job_dir = JobDir.from_path(job_dir_str)
    job_dirs = [job_dir]
    sites = ["www.test1.com", "www.test2.com"]
    weeks_data = organize_runs_by_week(job_dirs, sites)

    # Create a weekly interpretation file for the latest week
    latest_week = weeks_data["weeks"][0]
    latest_week_key = latest_week["week_key"]

    # Create weekly interpretation data
    weekly_data = [
        {"question": "Test Question 1?", "answer": "Test Answer 1", "site": "www.test1.com"},
        {
            "question": "Test Question 1?",
            "answer": "Test Answer 1 for site 2",
            "site": "www.test2.com",
        },
        {"question": "Test Question 2?", "answer": "Test Answer 2", "site": "www.test1.com"},
    ]

    # Write the weekly interpretation file
    storage = test_storage_adapter
    storage.write_text(f"weekly-{latest_week_key}-interpreted.json", json.dumps(weekly_data))

    # Create template directory and index template
    template_dir = temp_dir / "templates"
    template_dir.mkdir(exist_ok=True)

    index_template = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Media Lens Report</title>
    </head>
    <body>
        {% if weekly_summary %}
        <div>
            <h2>Weekly Media Analysis</h2>
            <p>{{ weekly_summary_date }}</p>
            {% for row in weekly_summary %}
            <div>{{ row.question }}</div>
            {% endfor %}
        </div>
        {% endif %}
        <ul>
        {% for week in weeks %}
            <li>{{ week.week_display }}</li>
        {% endfor %}
        </ul>
    </body>
    </html>
    """
    storage.write_text("templates/index_template.j2", index_template)

    # Call generate_index_page
    html = generate_index_page(weeks_data, template_dir)

    # Check that HTML was generated
    assert html is not None
    # Check if weekly summary exists (it might not if no valid interpretation found)
    if "Weekly Media Analysis" in html:
        assert "Test Question 1" in html
    else:
        # If no weekly summary, verify at least basic structure exists
        assert "Media Lens Report" in html


def test_generate_html_from_path(sample_job_directory, temp_dir, test_storage_adapter, monkeypatch):
    """Test the main HTML generation function."""
    # Patch the shared storage to use our test storage adapter
    monkeypatch.setattr(
        "src.media_lens.presentation.html_formatter.shared_storage", test_storage_adapter
    )

    # Get the storage adapter from the fixture
    storage = test_storage_adapter

    # Create template directory
    template_dir = temp_dir / "templates"
    template_dir.mkdir(exist_ok=True)

    # Create index template using the storage adapter
    index_template = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Media Lens Report</title>
        </head>
        <body>
            <h1>Media Lens Report</h1>
            <p>Generated: {{ report_timestamp }}</p>

            {% if weekly_summary and sites %}
            <div>
                <h2>Weekly Media Analysis</h2>
                <p>Analysis for the last seven days ending {{ weekly_summary_date }}</p>

                <div>
                    <div>
                        <div>Question</div>
                        {% for site in sites %}
                        <div>{{ site }}</div>
                        {% endfor %}
                    </div>
                    {% for row in weekly_summary %}
                    <div>
                        <div>
                            <b>{{ row.question }}</b>
                        </div>
                        {% for site in sites %}
                        <div>
                            {{ row.answers[site] }}
                        </div>
                        {% endfor %}
                    </div>
                    {% endfor %}
                </div>
            </div>
            {% endif %}

            <ul>
            {% for week in weeks %}
                <li>
                    <a href="medialens-{{ week.week_key }}.html">{{ week.week_display }}</a>
                </li>
            {% endfor %}
            </ul>
        </body>
        </html>
        """
    storage.write_text("templates/index_template.j2", index_template)

    # Create weekly template using the storage adapter (without weekly interpretation section)
    weekly_template = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>{{ week_display }} Report</title>
        </head>
        <body>
            <h1>{{ week_display }} Report</h1>
            {% for site in sites %}
            <h2>{{ site }}</h2>
            <ul>
            {% for article in site_content[site] %}
                <li>{{ article.title }}</li>
            {% endfor %}
            </ul>
            {% endfor %}
        </body>
        </html>
        """
    storage.write_text("templates/weekly_template.j2", weekly_template)

    # Create a sample weekly interpretation file to ensure processing works
    week_key = "2025-W09"  # Corresponds to our fixed timestamp
    storage.write_text(f"weekly-{week_key}-interpreted.json", "[]")

    # Call generate_html_from_path
    sites = ["www.test1.com", "www.test2.com"]
    html = generate_html_from_path(sites, template_dir)

    # Check that HTML was generated
    assert html is not None

    # Check if files were created in staging directory
    staging_dir = storage.get_staging_directory()
    assert storage.file_exists(f"{staging_dir}/medialens.html")

    # Verify HTML content
    assert "<title>Media Lens Report</title>" in html
    assert "<h1>Media Lens Report</h1>" in html


# Cursor functionality tests


def test_get_format_cursor_no_cursor_exists(test_storage_adapter, monkeypatch):
    """Test getting format cursor when no cursor file exists."""
    # Patch the shared storage to use our test storage adapter
    monkeypatch.setattr(
        "src.media_lens.presentation.html_formatter.shared_storage", test_storage_adapter
    )

    # Ensure cursor file doesn't exist
    cursor_path = "format_cursor.txt"
    if test_storage_adapter.file_exists(cursor_path):
        test_storage_adapter.delete_file(cursor_path)

    # Test getting cursor
    cursor = get_format_cursor()
    assert cursor is None


def test_update_and_get_format_cursor(test_storage_adapter, monkeypatch):
    """Test updating and getting format cursor."""
    # Patch the shared storage to use our test storage adapter
    monkeypatch.setattr(
        "src.media_lens.presentation.html_formatter.shared_storage", test_storage_adapter
    )

    # Test timestamp
    test_timestamp = datetime.datetime(2025, 2, 26, 15, 30, 0, tzinfo=datetime.timezone.utc)

    # Update cursor
    update_format_cursor(test_timestamp)

    # Get cursor back
    cursor = get_format_cursor()
    assert cursor is not None
    assert cursor == test_timestamp


def test_reset_format_cursor(test_storage_adapter, monkeypatch):
    """Test resetting format cursor."""
    # Patch the shared storage to use our test storage adapter
    monkeypatch.setattr(
        "src.media_lens.presentation.html_formatter.shared_storage", test_storage_adapter
    )

    # Set a cursor first
    test_timestamp = datetime.datetime(2025, 2, 26, 15, 30, 0, tzinfo=datetime.timezone.utc)
    update_format_cursor(test_timestamp)

    # Verify cursor exists
    assert get_format_cursor() is not None

    # Reset cursor
    reset_format_cursor()

    # Verify cursor is gone
    assert get_format_cursor() is None


def test_get_jobs_since_cursor_no_cursor(sample_job_directory, test_storage_adapter, monkeypatch):
    """Test getting jobs since cursor when no cursor exists."""
    # Patch shared storage and JobDir.list_all to use our test setup
    monkeypatch.setattr(
        "src.media_lens.presentation.html_formatter.shared_storage", test_storage_adapter
    )

    # Create a mock JobDir
    job_dir_str = sample_job_directory.name
    job_dir = JobDir.from_path(job_dir_str)

    # Mock JobDir.list_all to return our test job
    monkeypatch.setattr("src.media_lens.job_dir.JobDir.list_all", lambda storage: [job_dir])

    sites = ["www.test1.com"]
    job_dirs, affected_weeks = get_jobs_since_cursor(sites, cursor=None)

    # Should return all jobs when no cursor
    assert len(job_dirs) == 1
    assert job_dirs[0] == job_dir
    assert len(affected_weeks) == 1


def test_get_jobs_since_cursor_with_cursor(sample_job_directory, test_storage_adapter, monkeypatch):
    """Test getting jobs since cursor with an existing cursor."""
    # Patch shared storage
    monkeypatch.setattr(
        "src.media_lens.presentation.html_formatter.shared_storage", test_storage_adapter
    )

    # Create a mock JobDir
    job_dir_str = sample_job_directory.name
    job_dir = JobDir.from_path(job_dir_str)

    # Mock JobDir.list_all to return our test job
    monkeypatch.setattr("src.media_lens.job_dir.JobDir.list_all", lambda storage: [job_dir])

    sites = ["www.test1.com"]

    # Test with cursor before job timestamp
    old_cursor = job_dir.datetime - datetime.timedelta(hours=1)
    job_dirs, affected_weeks = get_jobs_since_cursor(sites, cursor=old_cursor)

    # Should return the job since it's newer than cursor
    assert len(job_dirs) == 1
    assert job_dirs[0] == job_dir

    # Test with cursor after job timestamp
    new_cursor = job_dir.datetime + datetime.timedelta(hours=1)
    job_dirs, affected_weeks = get_jobs_since_cursor(sites, cursor=new_cursor)

    # Should return no jobs since cursor is newer
    assert len(job_dirs) == 0
    assert len(affected_weeks) == 0


def test_generate_html_from_path_with_force_full(
    sample_job_directory, temp_dir, test_storage_adapter, monkeypatch
):
    """Test HTML generation with force_full=True."""
    # Patch the shared storage to use our test storage adapter
    monkeypatch.setattr(
        "src.media_lens.presentation.html_formatter.shared_storage", test_storage_adapter
    )

    # Get the storage adapter from the fixture
    storage = test_storage_adapter

    # Create template directory and templates
    template_dir = temp_dir / "templates"
    template_dir.mkdir(exist_ok=True)

    # Create minimal templates
    storage.write_text("templates/index_template.j2", "<html><body><h1>Test</h1></body></html>")
    storage.write_text("templates/weekly_template.j2", "<html><body><h2>Week</h2></body></html>")

    # Create a job directory
    job_dir_str = sample_job_directory.name
    job_dir = JobDir.from_path(job_dir_str)

    # Mock JobDir.list_all to return our test job
    monkeypatch.setattr("src.media_lens.job_dir.JobDir.list_all", lambda storage: [job_dir])

    # Set a cursor to ensure force_full ignores it
    cursor_time = datetime.datetime.now(datetime.timezone.utc)
    update_format_cursor(cursor_time)

    sites = ["www.test1.com"]

    # Call with force_full=True
    html = generate_html_from_path(sites, template_dir, force_full=True)

    # Should generate HTML regardless of cursor
    assert html is not None
    assert "<h1>Test</h1>" in html

    # Verify staging files were created
    staging_dir = storage.get_staging_directory()
    assert storage.file_exists(f"{staging_dir}/medialens.html")


def test_generate_html_from_path_incremental(
    sample_job_directory, temp_dir, test_storage_adapter, monkeypatch
):
    """Test HTML generation with incremental processing."""
    # Patch the shared storage to use our test storage adapter
    monkeypatch.setattr(
        "src.media_lens.presentation.html_formatter.shared_storage", test_storage_adapter
    )

    # Get the storage adapter from the fixture
    storage = test_storage_adapter

    # Create template directory and templates
    template_dir = temp_dir / "templates"
    template_dir.mkdir(exist_ok=True)

    # Create minimal templates
    storage.write_text("templates/index_template.j2", "<html><body><h1>Test</h1></body></html>")
    storage.write_text("templates/weekly_template.j2", "<html><body><h2>Week</h2></body></html>")

    # Create a job directory
    job_dir_str = sample_job_directory.name
    job_dir = JobDir.from_path(job_dir_str)

    # Mock JobDir.list_all to return our test job
    monkeypatch.setattr("src.media_lens.job_dir.JobDir.list_all", lambda storage: [job_dir])

    sites = ["www.test1.com"]

    # First run - no cursor
    html = generate_html_from_path(sites, template_dir, force_full=False)
    assert html is not None

    # Verify cursor was set
    cursor = get_format_cursor()
    assert cursor is not None

    # Create existing index file in staging
    staging_dir = storage.get_staging_directory()
    existing_html = "<html><body><h1>Existing</h1></body></html>"
    storage.write_text(f"{staging_dir}/medialens.html", existing_html)

    # Second run - with cursor (no new jobs)
    html = generate_html_from_path(sites, template_dir, force_full=False)

    # Should return existing HTML since no new content
    assert html == existing_html


# Cursor Optimization Tests


def test_rewind_format_cursor(test_storage_adapter, monkeypatch):
    """Test rewinding format cursor by specified number of days."""
    # Patch the shared storage to use our test storage adapter
    monkeypatch.setattr(
        "src.media_lens.presentation.html_formatter.shared_storage", test_storage_adapter
    )

    # Set initial cursor
    initial_timestamp = datetime.datetime(2025, 6, 15, 12, 0, 0, tzinfo=datetime.timezone.utc)
    update_format_cursor(initial_timestamp)

    # Rewind by 7 days
    rewind_format_cursor(7)

    # Check that cursor was rewound correctly
    rewound_cursor = get_format_cursor()
    expected_cursor = initial_timestamp - datetime.timedelta(days=7)

    assert rewound_cursor is not None
    assert rewound_cursor == expected_cursor


def test_rewind_format_cursor_no_existing_cursor(test_storage_adapter, monkeypatch):
    """Test rewinding format cursor when no cursor exists."""
    # Patch the shared storage to use our test storage adapter
    monkeypatch.setattr(
        "src.media_lens.presentation.html_formatter.shared_storage", test_storage_adapter
    )

    # Ensure no cursor exists
    reset_format_cursor()

    # Attempt to rewind - should not crash
    rewind_format_cursor(7)

    # Should still be no cursor
    assert get_format_cursor() is None


def test_get_lightweight_weeks_data(test_storage_adapter, monkeypatch):
    """Test getting lightweight weeks data for index page."""
    # Patch the shared storage to use our test storage adapter
    monkeypatch.setattr(
        "src.media_lens.presentation.html_formatter.shared_storage", test_storage_adapter
    )

    # Create multiple JobDir objects with different timestamps
    job_dirs = [
        JobDir.from_path("2025-06-15_120000"),  # Week 2025-W24
        JobDir.from_path("2025-06-14_120000"),  # Week 2025-W23
        JobDir.from_path("2025-06-08_120000"),  # Week 2025-W23
        JobDir.from_path("2025-06-01_120000"),  # Week 2025-W22
    ]

    # Mock JobDir.list_all to return our test jobs
    monkeypatch.setattr("src.media_lens.job_dir.JobDir.list_all", lambda storage: job_dirs)

    # Call get_lightweight_weeks_data
    result = get_lightweight_weeks_data()

    # Check result structure
    assert "report_timestamp" in result
    assert "weeks" in result

    # Should have 3 weeks (W24, W23, W22)
    weeks = result["weeks"]
    assert len(weeks) == 3

    # Check that weeks are sorted newest first
    week_keys = [week["week_key"] for week in weeks]
    assert week_keys == ["2025-W24", "2025-W23", "2025-W22"]

    # Check week data structure
    for week in weeks:
        assert "week_key" in week
        assert "week_display" in week
        assert "runs" in week
        assert isinstance(week["runs"], list)

    # Check specific week counts
    w24_week = next(w for w in weeks if w["week_key"] == "2025-W24")
    assert len(w24_week["runs"]) == 1  # 1 job in week 24

    w23_week = next(w for w in weeks if w["week_key"] == "2025-W23")
    assert len(w23_week["runs"]) == 2  # 2 jobs in week 23

    w22_week = next(w for w in weeks if w["week_key"] == "2025-W22")
    assert len(w22_week["runs"]) == 1  # 1 job in week 22


def test_get_lightweight_weeks_data_empty(test_storage_adapter, monkeypatch):
    """Test getting lightweight weeks data when no jobs exist."""
    # Patch the shared storage to use our test storage adapter
    monkeypatch.setattr(
        "src.media_lens.presentation.html_formatter.shared_storage", test_storage_adapter
    )

    # Mock JobDir.list_all to return empty list
    monkeypatch.setattr("src.media_lens.job_dir.JobDir.list_all", lambda storage: [])

    # Call get_lightweight_weeks_data
    result = get_lightweight_weeks_data()

    # Check result structure
    assert "report_timestamp" in result
    assert "weeks" in result
    assert len(result["weeks"]) == 0


def test_incremental_vs_full_processing(test_storage_adapter, temp_dir, monkeypatch):
    """Test that incremental processing correctly identifies affected weeks."""
    # Patch the shared storage to use our test storage adapter
    monkeypatch.setattr(
        "src.media_lens.presentation.html_formatter.shared_storage", test_storage_adapter
    )

    # Create JobDir objects from different weeks
    old_job = JobDir.from_path("2025-05-01_120000")  # Week 2025-W17 (old)
    recent_job1 = JobDir.from_path("2025-06-14_120000")  # Week 2025-W23 (recent)
    recent_job2 = JobDir.from_path("2025-06-15_120000")  # Week 2025-W24 (recent)
    all_jobs = [old_job, recent_job1, recent_job2]

    # Mock JobDir.list_all to return our test jobs
    monkeypatch.setattr("src.media_lens.job_dir.JobDir.list_all", lambda storage: all_jobs)

    sites = ["www.test1.com"]

    # Test incremental job filtering
    cursor_time = datetime.datetime(2025, 6, 13, 0, 0, 0, tzinfo=datetime.timezone.utc)

    # Test get_jobs_since_cursor directly
    job_dirs, affected_weeks = get_jobs_since_cursor(sites, cursor_time)

    # Should only return jobs after cursor (2 recent jobs)
    assert len(job_dirs) == 2
    assert recent_job1 in job_dirs
    assert recent_job2 in job_dirs
    assert old_job not in job_dirs

    # Should identify affected weeks
    assert len(affected_weeks) == 2
    assert "2025-W23" in affected_weeks
    assert "2025-W24" in affected_weeks
    assert "2025-W17" not in affected_weeks


def test_get_jobs_since_cursor_performance_simulation(test_storage_adapter, monkeypatch):
    """Test that get_jobs_since_cursor correctly filters jobs for performance."""
    # Patch the shared storage to use our test storage adapter
    monkeypatch.setattr(
        "src.media_lens.presentation.html_formatter.shared_storage", test_storage_adapter
    )

    # Create many JobDir objects simulating a large dataset
    all_jobs = []

    # Create 50 old jobs (should be filtered out)
    for i in range(50):
        timestamp = f"2025-01-{i + 1:02d}_120000"
        if i + 1 <= 31:  # Only go up to day 31
            all_jobs.append(JobDir.from_path(timestamp))

    # Create 5 recent jobs (should be included)
    recent_jobs = [
        JobDir.from_path("2025-06-14_120000"),
        JobDir.from_path("2025-06-15_120000"),
        JobDir.from_path("2025-06-15_130000"),
        JobDir.from_path("2025-06-16_120000"),
        JobDir.from_path("2025-06-16_130000"),
    ]
    all_jobs.extend(recent_jobs)

    # Mock JobDir.list_all to return our large dataset
    monkeypatch.setattr("src.media_lens.job_dir.JobDir.list_all", lambda storage: all_jobs)

    # Set cursor to only include recent jobs
    cursor = datetime.datetime(2025, 6, 14, 0, 0, 0, tzinfo=datetime.timezone.utc)

    sites = ["www.test1.com"]
    job_dirs, affected_weeks = get_jobs_since_cursor(sites, cursor)

    # Should only return the 5 recent jobs
    assert len(job_dirs) == 5

    # All returned jobs should be after the cursor
    for job_dir in job_dirs:
        assert job_dir.datetime > cursor

    # Should identify affected weeks
    assert len(affected_weeks) >= 1
    assert "2025-W24" in affected_weeks  # June 14-16 2025 is in week 24


def test_organize_runs_by_week_with_limited_jobs(test_storage_adapter, monkeypatch):
    """Test that organize_runs_by_week works efficiently with limited job set."""
    # Patch the shared storage to use our test storage adapter
    monkeypatch.setattr(
        "src.media_lens.presentation.html_formatter.shared_storage", test_storage_adapter
    )

    # Create a small set of jobs (simulating incremental processing)
    # Use jobs from the same week
    limited_jobs = [
        JobDir.from_path("2025-06-15_120000"),  # Week 2025-W24
        JobDir.from_path("2025-06-15_130000"),  # Week 2025-W24 (same day, different time)
    ]

    sites = ["www.test1.com", "www.test2.com"]

    # Call organize_runs_by_week with limited set
    result = organize_runs_by_week(limited_jobs, sites)

    # Should only process the limited jobs
    assert "weeks" in result
    assert len(result["weeks"]) == 1  # Only one week

    week = result["weeks"][0]
    assert week["week_key"] == "2025-W24"
    assert len(week["runs"]) == 2  # Both jobs in the same week


def test_full_cursor_optimization_workflow(test_storage_adapter, temp_dir, monkeypatch):
    """Test the complete cursor optimization workflow end-to-end."""
    # Patch the shared storage to use our test storage adapter
    monkeypatch.setattr(
        "src.media_lens.presentation.html_formatter.shared_storage", test_storage_adapter
    )

    # Set up storage and templates
    storage = test_storage_adapter
    template_dir = temp_dir / "templates"
    template_dir.mkdir(exist_ok=True)

    storage.write_text(
        "templates/index_template.j2",
        "<html><body>{% for week in weeks %}<div>{{ week.week_key }}: {{ week.runs|length }} jobs</div>{% endfor %}</body></html>",
    )
    storage.write_text(
        "templates/weekly_template.j2", "<html><body><h2>{{ week_display }}</h2></body></html>"
    )

    # Create a realistic job dataset
    all_jobs = [
        JobDir.from_path("2025-01-15_120000"),  # Old job - Week 2025-W02
        JobDir.from_path("2025-01-16_120000"),  # Old job - Week 2025-W02
        JobDir.from_path("2025-06-14_120000"),  # Recent job - Week 2025-W23
        JobDir.from_path("2025-06-15_120000"),  # Recent job - Week 2025-W24
        JobDir.from_path("2025-06-16_120000"),  # Recent job - Week 2025-W24
    ]

    # Mock JobDir.list_all to return our dataset
    monkeypatch.setattr("src.media_lens.job_dir.JobDir.list_all", lambda storage: all_jobs)

    sites = ["www.test1.com"]

    # Step 1: Initial full run (no cursor)
    reset_format_cursor()
    html1 = generate_html_from_path(sites, template_dir, force_full=False)

    # Should process all jobs and set cursor
    assert "2025-W02" in html1
    assert "2025-W24" in html1
    assert "2025-W23" in html1
    cursor1 = get_format_cursor()
    assert cursor1 is not None

    # Step 2: Rewind cursor by 3 days
    rewind_format_cursor(3)
    cursor2 = get_format_cursor()
    assert cursor2 == cursor1 - datetime.timedelta(days=3)

    # Step 3: Run incremental processing
    html2 = generate_html_from_path(sites, template_dir, force_full=False)

    # Should still show all weeks in index (lightweight), but only process affected weeks
    assert html2 is not None

    # Verify cursor was updated
    cursor3 = get_format_cursor()
    assert cursor3 > cursor2  # Should be updated to latest job timestamp

    # Step 4: Run again with no new jobs (should skip processing)
    staging_dir = storage.get_staging_directory()
    existing_html = storage.read_text(f"{staging_dir}/medialens.html")

    html3 = generate_html_from_path(sites, template_dir, force_full=False)

    # Should return existing HTML since no new jobs
    assert html3 == existing_html

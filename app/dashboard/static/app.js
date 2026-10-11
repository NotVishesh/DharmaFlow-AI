// DharmaFlow AI — Dashboard Frontend JavaScript

document.addEventListener("DOMContentLoaded", () => {
  setupNavigation();
  loadOverview();
});

let currentJobId = null;

function setupNavigation() {
  document.querySelectorAll(".nav-link").forEach(link => {
    link.addEventListener("click", () => {
      document.querySelectorAll(".nav-link").forEach(l => l.classList.remove("active"));
      document.querySelectorAll(".content-pane").forEach(p => p.classList.remove("active"));

      link.classList.add("active");
      const tab = link.getAttribute("data-tab");
      const targetPane = document.getElementById(`pane-${tab}`);
      if (targetPane) {
        targetPane.classList.add("active");
        document.getElementById("page-title").textContent = link.textContent.trim();
        loadTabContent(tab);
      }
    });
  });
}

function loadTabContent(tab) {
  if (tab === "overview") loadOverview();
  else if (tab === "content-studio") loadContentStudio();
  else if (tab === "video-studio") loadVideoStudio();
  else if (tab === "publishing") loadPublishing();
  else if (tab === "analytics") loadAnalytics();
  else if (tab === "settings") loadSettings();
}

function refreshCurrentTab() {
  const activeLink = document.querySelector(".nav-link.active");
  if (activeLink) loadTabContent(activeLink.getAttribute("data-tab"));
}

async function loadOverview() {
  try {
    const res = await fetch("/api/dashboard/overview");
    const data = await res.json();

    document.getElementById("kpi-ideas").textContent = data.total_ideas || 0;
    document.getElementById("kpi-completed").textContent = data.jobs_completed || 0;
    document.getElementById("kpi-pending").textContent = data.pending_approval || 0;
    document.getElementById("kpi-published").textContent = data.published || 0;

    const tbody = document.getElementById("recent-jobs-table");
    tbody.innerHTML = "";
    if (!data.recent_jobs || data.recent_jobs.length === 0) {
      tbody.innerHTML = "<tr><td colspan='4' style='text-align:center;'>No jobs generated yet.</td></tr>";
      return;
    }

    data.recent_jobs.forEach(job => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td style="font-family: monospace;">${job.id}</td>
        <td><span class="status-badge status-${job.status}">${job.status}</span></td>
        <td>${job.topic}</td>
        <td><button class="btn btn-secondary" style="padding:4px 8px; font-size:12px;" onclick="viewJob('${job.id}')">View</button></td>
      `;
      tbody.appendChild(tr);
    });
  } catch (err) {
    console.error("Failed to load overview:", err);
  }
}

async function loadContentStudio() {
  try {
    const res = await fetch("/api/content/scripts");
    const scripts = await res.json();
    const tbody = document.getElementById("scripts-table");
    tbody.innerHTML = "";
    if (scripts.length === 0) {
      tbody.innerHTML = "<tr><td colspan='4' style='text-align:center;'>No scripts saved.</td></tr>";
      return;
    }
    scripts.forEach(s => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td style="font-family: monospace;">${s.id.substring(0, 8)}</td>
        <td>${s.topic}</td>
        <td>${s.category}</td>
        <td><span class="status-badge status-${s.status}">${s.status}</span></td>
      `;
      tbody.appendChild(tr);
    });
  } catch (err) {
    console.error(err);
  }
}

async function triggerGenerate() {
  const topic = document.getElementById("gen-topic").value.trim();
  if (!topic) {
    alert("Please enter a video topic.");
    return;
  }
  const category = document.getElementById("gen-category").value;
  const language = document.getElementById("gen-language").value;
  const duration = parseInt(document.getElementById("gen-duration").value, 10);
  const demoMode = document.getElementById("gen-mode").value === "demo";

  try {
    const res = await fetch("/api/content/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        topic: topic,
        category: category,
        language: language,
        duration_seconds: duration,
        demo_mode: demoMode,
      }),
    });
    const data = await res.json();
    alert(`Pipeline launched! Job ID: ${data.job_id}\nCheck Video Studio for progress.`);
    loadOverview();
  } catch (err) {
    alert("Failed to start pipeline: " + err.message);
  }
}

async function loadVideoStudio() {
  try {
    const res = await fetch("/api/jobs/");
    const jobs = await res.json();
    const tbody = document.getElementById("video-jobs-table");
    tbody.innerHTML = "";
    if (jobs.length === 0) {
      tbody.innerHTML = "<tr><td colspan='5' style='text-align:center;'>No video renders found.</td></tr>";
      return;
    }
    jobs.forEach(j => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td style="font-family: monospace;">${j.id.substring(0, 8)}</td>
        <td>${j.topic}</td>
        <td><span class="status-badge status-${j.status}">${j.status}</span></td>
        <td>${j.duration_seconds ? j.duration_seconds.toFixed(1) + "s" : "N/A"}</td>
        <td><button class="btn btn-secondary" style="padding:4px 8px; font-size:12px;" onclick="inspectJob('${j.id}')">Inspect</button></td>
      `;
      tbody.appendChild(tr);
    });
  } catch (err) {
    console.error(err);
  }
}

async function inspectJob(jobId) {
  currentJobId = jobId;
  try {
    const res = await fetch(`/api/jobs/${jobId}`);
    const data = await res.json();
    document.getElementById("video-detail-card").style.display = "block";
    document.getElementById("current-job-title").textContent = `Inspection: ${data.script ? data.script.topic : jobId}`;
    document.getElementById("vdetail-status").textContent = data.status;
    document.getElementById("vdetail-duration").textContent = data.duration_seconds || "N/A";
    document.getElementById("vdetail-qc").textContent = data.qc ? `${data.qc.score}% (${data.qc.passed ? "PASSED" : "FAILED"})` : "N/A";
    document.getElementById("vdetail-path").textContent = data.output_path || "N/A";

    const pubInput = document.getElementById("pub-job-id");
    if (pubInput) pubInput.value = jobId;
  } catch (err) {
    alert("Failed to fetch job details: " + err.message);
  }
}

async function approveJob() {
  if (!currentJobId) return;
  try {
    const res = await fetch(`/api/jobs/${currentJobId}/approve`, { method: "POST" });
    if (res.ok) {
      alert("Job approved! Ready for publishing.");
      loadVideoStudio();
    } else {
      const err = await res.json();
      alert("Approval failed: " + err.detail);
    }
  } catch (err) {
    alert("Error: " + err.message);
  }
}

async function rejectJob() {
  if (!currentJobId) return;
  const reason = prompt("Enter reason for rejection:");
  if (reason === null) return;
  try {
    const res = await fetch(`/api/jobs/${currentJobId}/reject?reason=${encodeURIComponent(reason)}`, { method: "POST" });
    if (res.ok) {
      alert("Job rejected.");
      loadVideoStudio();
    }
  } catch (err) {
    alert("Error: " + err.message);
  }
}

async function loadPublishing() {
  try {
    const res = await fetch("/api/publishing/status");
    const data = await res.json();
    document.getElementById("yt-conn-status").textContent = data.youtube.authenticated ? "✓ Authenticated" : "✗ Not Authenticated";
    document.getElementById("yt-conn-status").style.color = data.youtube.authenticated ? "var(--accent-green)" : "var(--accent-red)";
    document.getElementById("ig-conn-status").textContent = data.instagram.enabled ? "Enabled" : "Disabled";
  } catch (err) {
    console.error(err);
  }
}

async function triggerPublish() {
  const jobId = document.getElementById("pub-job-id").value.trim();
  const platform = document.getElementById("pub-platform").value;
  const privacy = document.getElementById("pub-privacy").value;
  if (!jobId) {
    alert("Please enter Job ID.");
    return;
  }
  try {
    const res = await fetch("/api/publishing/publish", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ job_id: jobId, platform: platform, privacy: privacy }),
    });
    const data = await res.json();
    if (res.ok) {
      alert(`Success! Published to ${platform}: ${data.url}`);
    } else {
      alert(`Publishing failed: ${data.detail}`);
    }
  } catch (err) {
    alert("Error: " + err.message);
  }
}

async function loadAnalytics() {
  try {
    const res = await fetch("/api/analytics/summary");
    const data = await res.json();
    document.getElementById("kpi-analytics-published").textContent = data.total_published || 0;
    document.getElementById("kpi-analytics-views").textContent = data.total_views || 0;
  } catch (err) {
    console.error(err);
  }
}

async function loadSettings() {
  try {
    const res = await fetch("/api/settings/diagnostics");
    const items = await res.json();
    const tbody = document.getElementById("diag-table");
    tbody.innerHTML = "";
    items.forEach(item => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td><strong>${item.name}</strong></td>
        <td><span class="status-badge" style="background-color:${item.ok ? 'rgba(16,185,129,0.15)' : 'rgba(239,68,68,0.15)'}; color:${item.ok ? 'var(--accent-green)' : 'var(--accent-red)'};">${item.ok ? "PASS" : "FAIL"}</span></td>
        <td style="color:var(--text-muted); font-size:13px;">${item.message}</td>
      `;
      tbody.appendChild(tr);
    });
  } catch (err) {
    console.error(err);
  }
}

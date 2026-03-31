let allNews = [];

/* =========================
   LIVE NEWS TICKER
========================= */
function updateTicker(newsList) {
    const ticker = document.getElementById("tickerContent");
    if (!ticker) return;

    if (!newsList || newsList.length === 0) {
        ticker.innerText = "⚡ No live news...";
        return;
    }

    let tickerText = newsList
        .slice(0, 10)
        .map(n => {
            let emoji =
                n.sentiment_label === "bullish" ? "🟢" :
                n.sentiment_label === "bearish" ? "🔴" : "⚪";
            return `${emoji} ${n.title}`;
        })
        .join("   🔸   ");

    ticker.innerText = tickerText;

    let length = tickerText.length;
    let duration = Math.max(40, length / 5);
    ticker.style.animation = `scrollTicker ${duration}s linear infinite`;
}

/* =========================
   SOCKET.IO CONNECTION (AUTO-DETECT HOST)
========================= */
const socket = io(window.location.origin);

socket.on("connect", () => {
    console.log("✅ Socket connected");
});

socket.on("news_update", (data) => {
    console.log("🔥 Live Update:", data);
    const news = data.news || data || [];
    allNews = [...news, ...allNews];
    renderNews(allNews);
    updateTicker(allNews);
});

socket.on("connect_error", (err) => {
    console.log("⚠️ Socket connection error (will retry):", err.message);
});

/* =========================
   FETCH + RENDER
========================= */
async function startScraping() {
    const loader = document.getElementById("loader");
    const container = document.getElementById("newsContainer");
    const btn = document.getElementById("scrapeBtn");

    loader.classList.remove("hidden");
    container.innerHTML = "";
    btn.disabled = true;
    btn.innerText = "⏳ Scraping...";

    try {
        const response = await fetch("/scrape");
        const data = await response.json();
        loader.classList.add("hidden");
        allNews = data;
        renderNews(data);
        updateTicker(data);
    } catch (error) {
        console.error("❌ Fetch Error:", error);
        loader.classList.add("hidden");
        container.innerHTML = "<p style='color:red;'>Failed to fetch news. Please try again.</p>";
    } finally {
        btn.disabled = false;
        btn.innerText = "🚀 Start Scraping";
    }
}

/* =========================
   RENDER FUNCTION
========================= */
function renderNews(newsList) {
    const container = document.getElementById("newsContainer");
    container.innerHTML = "";

    if (!newsList || newsList.length === 0) {
        container.innerHTML = "<p style='text-align:center; color:#888;'>No news found. Click Start Scraping!</p>";
        return;
    }

    newsList.forEach(news => {
        const card = document.createElement("div");
        card.className = "card";
        card.innerHTML = `
            <h3>${news.title}</h3>
            <p><b>Source:</b> ${news.source}</p>
            <p><b>Impact:</b> <span class="impact-${news.impact.toLowerCase()}">${news.impact}</span></p>
            <p class="${news.sentiment_label}">
                <b>Sentiment:</b> ${news.sentiment_label}
            </p>
            <div class="overlay">
                <p><b>Summary:</b> ${news.summary || "N/A"}</p>
                <p><b>Score:</b> ${news.score}</p>
                <p><b>Risk:</b> ${getRisk(news)}</p>
                <p><b>Market Effect:</b> ${getMarketEffect(news)}</p>
                <a href="${news.link}" target="_blank">Read Full News →</a>
            </div>
        `;
        container.appendChild(card);
    });
}

/* =========================
   FILTER BY SOURCE
========================= */
function filterSource(source) {
    if (source === "ALL") {
        renderNews(allNews);
    } else {
        const filtered = allNews.filter(n => n.source === source);
        renderNews(filtered);
    }
}

/* =========================
   RISK LOGIC
========================= */
function getRisk(news) {
    if (news.impact === "HIGH" && news.sentiment_label === "bearish") {
        return "HIGH RISK 🔴";
    }
    if (news.impact === "HIGH") {
        return "VOLATILE ⚠️";
    }
    return "LOW RISK 🟢";
}

/* =========================
   MARKET EFFECT
========================= */
function getMarketEffect(news) {
    if (news.sentiment_label === "bullish") {
        return "Market Likely UP 📈";
    }
    if (news.sentiment_label === "bearish") {
        return "Market Likely DOWN 📉";
    }
    return "Sideways 🤝";
}

/* =========================
   SEARCH FUNCTION
========================= */
function searchNews() {
    const input = document.getElementById("searchBox");
    if (!input) return;
    const text = input.value.toLowerCase();
    const filtered = allNews.filter(n =>
        (n.title && n.title.toLowerCase().includes(text)) ||
        (n.summary && n.summary.toLowerCase().includes(text)) ||
        (n.source && n.source.toLowerCase().includes(text))
    );
    renderNews(filtered);
}

/* =========================
   ACTIVE BUTTON HIGHLIGHT
========================= */
function setActiveButton(clickedBtn) {
    document.querySelectorAll("nav button, .filters button")
        .forEach(btn => btn.classList.remove("active"));
    clickedBtn.classList.add("active");
}

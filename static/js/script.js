/* ============================
   1. MODAL TOGGLE FUNCTIONS
   ============================ */

function toggleModal() {
  const el = document.getElementById("transactionModal");
  if (el) el.classList.toggle("hidden");
}

function toggleGoalModal() {
  const el = document.getElementById("goalModal");
  if (el) el.classList.toggle("hidden");
}

function toggleSubModal() {
  const el = document.getElementById("subModal");
  if (el) el.classList.toggle("hidden");
}

function closeRoast() {
  const el = document.getElementById("roastModal");
  if (el) el.classList.add("hidden");
}

/* ============================
   2. AI ROAST FUNCTION
   ============================ */

async function getRoast() {
  const modal = document.getElementById("roastModal");
  const text = document.getElementById("roastText");

  // Show modal immediately
  if (modal) modal.classList.remove("hidden");

  // Set loading text
  if (text) text.innerText = "Consulting the Council of High Finance...";

  try {
    const response = await fetch("/roast_me");
    const data = await response.json();

    if (text) text.innerText = `"${data.roast}"`;
  } catch (error) {
    console.error("Roast Error:", error);
    if (text) text.innerText = "Even the AI is speechless at your spending.";
  }
}

/* ============================
   3. CHART INITIALIZATION
   ============================ */

function initChart(labels, data) {
  // Check if the canvas element exists before trying to draw
  const chartCanvas = document.getElementById("expenseChart");

  if (!chartCanvas) return; // Stop if no chart on this page

  const ctx = chartCanvas.getContext("2d");

  if (labels && labels.length > 0) {
    new Chart(ctx, {
      type: "doughnut",
      data: {
        labels: labels,
        datasets: [
          {
            data: data,
            backgroundColor: [
              "#06b6d4", // Cyan
              "#8b5cf6", // Violet
              "#ec4899", // Pink
              "#f59e0b", // Amber
              "#10b981", // Emerald
              "#3b82f6", // Blue
            ],
            borderWidth: 0,
            hoverOffset: 15,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        cutout: "75%",
        plugins: {
          legend: {
            position: "bottom",
            labels: {
              color: "#94a3b8",
              font: { size: 10, family: "Outfit" },
              usePointStyle: true,
              boxWidth: 8,
            },
          },
        },
        animation: { animateScale: true, animateRotate: true },
      },
    });
  } else {
    // Fallback for empty data
    ctx.font = "14px Outfit";
    ctx.fillStyle = "#64748b";
    ctx.textAlign = "center";
    ctx.fillText(
      "No expenses logged",
      ctx.canvas.width / 2,
      ctx.canvas.height / 2
    );
  }
}

const config = window.yourTurnConfig;
const euro = new Intl.NumberFormat("en", { style: "currency", currency: "EUR" });

async function api(base, path, options) {
  const response = await fetch(base + path, {
    signal: AbortSignal.timeout(6000),
    ...options,
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.error || "Service unavailable. Try again shortly.");
  }
  return response.status === 204 ? null : response.json();
}

function table(target, headings, rows) {
  const element = document.createElement("table");
  const heading = element.createTHead().insertRow();
  for (const label of headings) {
    const cell = document.createElement("th");
    cell.scope = "col";
    cell.textContent = label;
    heading.append(cell);
  }
  const body = element.createTBody();
  for (const values of rows) {
    const row = body.insertRow();
    for (const value of values) {
      const cell = row.insertCell();
      if (value instanceof Node) cell.append(value);
      else cell.textContent = value;
    }
  }
  target.replaceChildren(element);
}

function logForm(domain, record, roommates) {
  if (!roommates.length) return "Unavailable";
  const isChore = domain === "chores";
  const form = document.createElement("form");
  const person = document.createElement("select");
  person.setAttribute("aria-label", "Roommate");
  for (const roommate of roommates) {
    person.add(new Option(roommate.name, roommate.id, false, roommate.id === record.next_person_id));
  }
  form.append(person);
  const price = document.createElement("input");
  if (!isChore) {
    Object.assign(price, { type: "number", min: "0.01", max: "1000", step: "0.01", required: true });
    price.setAttribute("aria-label", "Price in euros");
    form.append(price);
  }
  const submit = document.createElement("button");
  submit.textContent = isChore ? "I did it" : "I bought it";
  form.append(submit);
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    submit.disabled = true;
    try {
      const payload = { roommate_id: Number(person.value) };
      if (!isChore) payload.price = Number(price.value);
      await api(config[domain], `/${domain}/${record.id}/${isChore ? "done" : "bought"}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      await load(domain);
    } catch (error) {
      document.querySelector(`#${domain} .message`).textContent = error.message;
    } finally {
      submit.disabled = false;
    }
  });
  return form;
}

async function load(domain) {
  const section = document.getElementById(domain);
  const message = section.querySelector(".message");
  const records = section.querySelector(".records");
  const totals = section.querySelector(".totals");
  message.textContent = "Loading…";
  try {
    const data = await api(config[domain], `/${domain}/`);
    if (domain === "chores") {
      table(records, ["Chore", "Schedule", "Last done", "Status", "Next up", "Log it"],
        data.chores.map((row) => [row.name, `Every ${row.frequency_days} day(s)`,
          row.last_done || "Never", row.days_overdue ? `${row.days_overdue} day(s) overdue` : "On time",
          row.next_person, logForm(domain, row, data.roommates)]));
      table(totals, ["Roommate", "Chores done"], data.stats.map((row) => [row.name, row.done]));
    } else {
      table(records, ["Supply", "Last bought", "Next up", "Log it"],
        data.supplies.map((row) => [row.name,
          row.last_bought ? `${row.last_bought} (${euro.format(row.last_price)})` : "Never",
          row.next_person || "Unavailable", logForm(domain, row, data.roommates)]));
      table(totals, ["Roommate", "Total"], data.spending.map((row) => [row.name, euro.format(row.spent)]));
    }
    message.textContent = data.warning || "";
  } catch (error) {
    records.replaceChildren();
    totals.replaceChildren();
    message.textContent = error.message;
  }
}

function showPage() {
  const domain = location.hash === "#supplies" ? "supplies" : "chores";
  document.getElementById("chores").hidden = domain !== "chores";
  document.getElementById("supplies").hidden = domain !== "supplies";
  load(domain);
}

const spending = document.getElementById("household-spending");
spending.parentElement.addEventListener("toggle", async () => {
  if (!spending.parentElement.open) return;
  spending.textContent = "Loading…";
  try {
    const data = await api(config.chores, "/chores/household-summary");
    table(spending, ["Roommate", "Total"], data.spending.map((row) => [row.name, euro.format(row.spent)]));
  } catch (error) {
    spending.textContent = error.message;
  }
});
window.addEventListener("hashchange", showPage);
showPage();

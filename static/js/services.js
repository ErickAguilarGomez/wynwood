


const parseServiceNumber = (value) => {
  let normalized = String(value ?? "").trim().replace(/\s/g, "").replace(/[^\d,.-]/g, "")
  if (normalized.includes(",") && normalized.includes(".")) {
    normalized = normalized.lastIndexOf(",") > normalized.lastIndexOf(".")
      ? normalized.replace(/\./g, "").replace(",", ".")
      : normalized.replace(/,/g, "")
  } else if (normalized.includes(",")) {
    normalized = normalized.replace(",", ".")
  }
  return Number(normalized)
}

const serviceMoney = (value) => {
  const amount = parseServiceNumber(value)
  return Number.isFinite(amount) ? String(Number(amount.toFixed(2))) : "0"
}

document.querySelectorAll(".svc-stepper").forEach((stepper) => {
  const input = stepper.querySelector('input[type="number"]')
  if (!input) return
  stepper.querySelectorAll("[data-step]").forEach((button) => {
    button.addEventListener("click", () => {
      const min = Number(input.min || 1)
      const max = Number(input.max || 99)
      const next = Number(input.value || min) + Number(button.dataset.step)
      input.value = String(Math.min(max, Math.max(min, next)))
      input.dispatchEvent(new Event("change", { bubbles: true }))
    })
  })
})

const setText = (node, text) => {
  if (node) node.textContent = text
}

const updateReservationTotal = (form) => {
  const serviceTotal = parseServiceNumber(form.querySelector("[data-quote-total]")?.textContent || 0)
  const baseTotal = parseServiceNumber(form.dataset.reservationTotal || 0)
  const existingAmount = parseServiceNumber(form.dataset.existingServiceAmount || 0)
  const total = document.querySelector("[data-reservation-total-display]")
  setText(total, serviceMoney(baseTotal - existingAmount + serviceTotal))
}

document.querySelectorAll('[data-service="transport"]').forEach((form) => {
  const quote = form.querySelector("[data-quote]")
  if (!quote) return
  const quantity = form.querySelector('input[name="quantity"]')
  const returnRow = form.querySelector('[data-trip-row="return"]')

  const isRoundTrip = () => {
    const checked = form.querySelector('input[name="trip_type"]:checked')
    return !checked || checked.value === "round_trip"
  }

  const update = () => {
    const vehicle = form.querySelector('input[name="vehicle"]:checked')
    if (!vehicle) return
    const roundTrip = isRoundTrip()
    const qty = Math.max(1, Number(quantity.value || 1))
    const passengers = Number(vehicle.dataset.passengers || 0) * qty
    const bags = Number(vehicle.dataset.bags || 0) * qty
    const total = parseServiceNumber(roundTrip ? vehicle.dataset.roundTrip : vehicle.dataset.oneWay) * qty

    setText(quote.querySelector("[data-quote-vehicle]"), vehicle.dataset.name || vehicle.value)
    setText(quote.querySelector("[data-quote-quantity]"), qty)
    setText(quote.querySelector("[data-quote-passengers]"), passengers)
    setText(quote.querySelector("[data-quote-bags]"), bags)
    setText(quote.querySelector("[data-quote-total]"), serviceMoney(total))
    if (returnRow) returnRow.classList.toggle("is-hidden", !roundTrip)
    updateReservationTotal(form)
  }

  form.querySelectorAll('input[name="trip_type"], input[name="vehicle"]').forEach((input) => {
    input.addEventListener("change", update)
  })
  if (quantity) quantity.addEventListener("change", update)
  update()
})

document.querySelectorAll('[data-service="groceries"]').forEach((form) => {
  const total = form.querySelector("[data-quote-total]")
  const selected = form.querySelector('input[name="pack"]:checked')
  if (selected) setText(total, serviceMoney(selected.dataset.price || 0))
  updateReservationTotal(form)
  form.querySelectorAll('input[name="pack"]').forEach((input) => {
    input.addEventListener("change", () => {
      if (input.checked) {
        setText(total, serviceMoney(input.dataset.price || 0))
        updateReservationTotal(form)
      }
    })
  })
})

document.querySelectorAll('[data-service="crib"]').forEach((form) => {
  const input = form.querySelector('input[name="quantity"]')
  const total = form.querySelector("[data-quote-total]")
  if (!input || !total) return
  const update = () => {
    const period = form.querySelector("[data-service-period]")
    const start = period && period.querySelector('input[name="start_date"]')
    const end = period && period.querySelector('input[name="end_date"]')
    let nights = Number(form.dataset.nights || 1)
    if (start && end) {
      const startDate = new Date(`${start.value}T00:00:00`)
      const endDate = new Date(`${end.value}T00:00:00`)
      nights = start.value && end.value && endDate > startDate
        ? Math.round((endDate - startDate) / 86400000)
        : 0
    }
    setText(total, serviceMoney(Number(form.dataset.unitPrice || 0) * Number(input.value || 1) * nights))
    updateReservationTotal(form)
  }
  input.addEventListener("change", update)
  const period = form.querySelector("[data-service-period]")
  if (period) period.addEventListener("daterangechange", update)
  update()
})

document.querySelectorAll('[data-service="flexible_checkin"]').forEach((form) => {
  updateReservationTotal(form)
})

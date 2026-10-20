const toggle = document.querySelector(".nav-toggle")
const navigation = document.querySelector(".main-nav")

document.querySelectorAll("[data-featured-filter]").forEach((form) => {
  let request

  form.addEventListener("submit", async (event) => {
    event.preventDefault()
    const button = event.submitter
    if (!button) return

    request?.abort()
    request = new AbortController()
    const url = new URL(form.action, window.location.href)
    url.searchParams.set("category", button.value)

    try {
      const response = await fetch(url, { signal: request.signal })
      if (!response.ok) throw new Error("Featured properties could not be loaded")
      const documentFromResponse = new DOMParser().parseFromString(await response.text(), "text/html")
      const nextTrack = documentFromResponse.querySelector(".featured-track")
      const track = document.querySelector(".featured-track")
      if (!nextTrack || !track) throw new Error("Featured properties could not be loaded")

      track.replaceChildren(...nextTrack.children)
      form.querySelectorAll('button[name="category"]').forEach((tab) => {
        const active = tab.value === button.value
        tab.classList.toggle("active", active)
        tab.setAttribute("aria-pressed", String(active))
      })

      const pageUrl = new URL(window.location.href)
      pageUrl.searchParams.set("category", button.value)
      pageUrl.hash = "stays"
      window.history.replaceState({ category: button.value }, "", pageUrl)
    } catch (error) {
      if (error.name !== "AbortError") window.location.assign(url)
    }
  })
})

if (toggle && navigation) {
  toggle.addEventListener("click", () => {
    const open = toggle.getAttribute("aria-expanded") === "true"
    toggle.setAttribute("aria-expanded", String(!open))
    navigation.classList.toggle("is-open", !open)
  })
}



document.querySelectorAll("[data-location-form]").forEach((form) => {
  const country = form.querySelector("[data-country-select]")
  const city = form.querySelector("[data-city-select]")
  const district = form.querySelector("[data-district-select]")
  if (!country || !city || !district) return

  const resetOptions = (select, label) => {
    select.replaceChildren(new Option(label, ""))
  }
  const loadCities = async (selectedCity = "") => {
    resetOptions(city, form.dataset.cityPlaceholder || "City or destination")
    resetOptions(district, form.dataset.districtPlaceholder || "District")
    if (!country.value) return
    const response = await fetch(`/api/locations/cities/?country=${encodeURIComponent(country.value)}`)
    if (!response.ok) return
    const data = await response.json()
    data.cities.forEach((item) => city.add(new Option(item.name, item.id, false, String(item.id) === String(selectedCity))))
  }
  const loadDistricts = async (selectedDistrict = "") => {
    resetOptions(district, form.dataset.districtPlaceholder || "District")
    if (!city.value) return
    const response = await fetch(`/api/locations/districts/?destination=${encodeURIComponent(city.value)}`)
    if (!response.ok) return
    const data = await response.json()
    data.districts.forEach((item) => district.add(new Option(item.name, item.name, false, item.name === selectedDistrict)))
  }

  country.addEventListener("change", () => loadCities())
  city.addEventListener("change", () => loadDistricts())


  if (country.value && city.value) loadDistricts(district.value)
  else if (country.value) loadCities(city.value)
})



document.querySelectorAll("[data-city-picker]").forEach((picker) => {
  const form = picker.closest("form")
  const isHeroPicker = Boolean(picker.closest(".search-bar-hero"))
  const cityInput = picker.querySelector("[data-city-input]")
  const countryInput = picker.querySelector("[data-city-country]")
  const cityLabel = picker.querySelector("[data-city-label]")
  const cityTrigger = picker.querySelector("[data-city-trigger]")
  const cityPanel = picker.querySelector("[data-city-panel]")
  const districtPicker = form ? form.querySelector("[data-district-picker]") : null
  if (!form || !cityInput || !countryInput || !cityLabel || !cityTrigger || !cityPanel) return

  const districtTrigger = districtPicker?.querySelector("[data-district-trigger]")
  const districtPanel = districtPicker?.querySelector("[data-district-panel]")
  const districtOptions = districtPicker?.querySelector("[data-district-options]")
  const districtEmpty = districtPicker?.querySelector("[data-district-empty]")
  const districtLabel = districtPicker?.querySelector("[data-district-label]")
  const hasDistrictPicker = Boolean(districtTrigger && districtPanel && districtOptions && districtEmpty && districtLabel)




  const positionGlobalPanel = (anchor, panel) => {
    const rect = anchor.getBoundingClientRect()
    const margin = 12
    const width = panel.offsetWidth
    const left = Math.max(margin, Math.min(rect.left, window.innerWidth - width - margin))
    panel.style.left = `${left + window.scrollX}px`
    panel.style.top = `${rect.bottom + margin + window.scrollY}px`
    panel.style.maxHeight = ""
  }
  if (isHeroPicker) {
    cityPanel.classList.add("global-search-panel")
    document.body.appendChild(cityPanel)
    if (hasDistrictPicker) {
      districtPanel.classList.add("global-search-panel")
      document.body.appendChild(districtPanel)
    }
  }

  const updateDistrictLabel = () => {
    if (!hasDistrictPicker) return
    const count = districtOptions.querySelectorAll('input[name="district"]:checked').length
    districtLabel.textContent = count ? `${count} ${count === 1 ? form.dataset.districtSingular : form.dataset.districtPlural}` : form.dataset.districtPlural
  }
  const loadDistricts = async () => {
    if (!hasDistrictPicker) return
    districtOptions.replaceChildren()
    districtEmpty.hidden = Boolean(cityInput.value)
    if (!cityInput.value) {
      updateDistrictLabel()
      return
    }
    const destinationId = cityInput.value
    const response = await fetch(`/api/locations/districts/?destination=${encodeURIComponent(destinationId)}`)
    if (!response.ok) return
    const data = await response.json()


    if (cityInput.value !== destinationId) return
    data.districts.forEach((item, index) => {
      const label = document.createElement("label")
      const input = document.createElement("input")
      const text = document.createElement("span")
      input.type = "checkbox"
      input.name = "district"
      input.value = item.name
      input.id = `district-${destinationId}-${index}`
      text.textContent = item.name
      input.addEventListener("change", updateDistrictLabel)
      label.append(input, text)
      districtOptions.append(label)
    })
    updateDistrictLabel()
  }
  const closeCity = () => {
    cityPanel.hidden = true
    cityTrigger.setAttribute("aria-expanded", "false")
  }
  const closeDistrict = () => {
    if (!hasDistrictPicker) return
    districtPanel.hidden = true
    districtTrigger.setAttribute("aria-expanded", "false")
  }

  cityTrigger.addEventListener("click", (event) => {
    event.stopPropagation()
    const open = cityPanel.hidden
    closeDistrict()
    cityPanel.hidden = !open
    cityTrigger.setAttribute("aria-expanded", String(open))
    if (open && isHeroPicker) positionGlobalPanel(cityTrigger, cityPanel)
  })
  cityPanel.addEventListener("click", (event) => {
    event.stopPropagation()
    const option = event.target.closest("[data-city-option]")
    if (!option) return
    cityInput.value = option.dataset.cityId
    countryInput.value = option.dataset.cityCountry
    cityLabel.textContent = option.dataset.cityName
    closeCity()
    loadDistricts()
  })
  if (hasDistrictPicker) {
    districtTrigger.addEventListener("click", (event) => {
      event.stopPropagation()
      const open = districtPanel.hidden
      closeCity()
      districtPanel.hidden = !open
      districtTrigger.setAttribute("aria-expanded", String(open))
      if (open && isHeroPicker) positionGlobalPanel(districtTrigger, districtPanel)
    })
    districtPanel.addEventListener("click", (event) => event.stopPropagation())
  }
  document.addEventListener("click", (event) => {
    if (!picker.contains(event.target) && !cityPanel.contains(event.target)) closeCity()
    if (hasDistrictPicker && !districtPicker.contains(event.target) && !districtPanel.contains(event.target)) closeDistrict()
  })

  if (cityInput.value && hasDistrictPicker) loadDistricts()
})



document.querySelectorAll("[data-results-filters]").forEach((form) => {
  const scopes = Array.from(form.querySelectorAll("[data-filter-scope]"))
  const cityInput = form.querySelector("[data-filter-city-input]")
  const countryInput = form.querySelector("[data-filter-country-input]")
  const cityLabel = form.querySelector("[data-filter-city-label]")
  const districtScope = form.querySelector(".filter-district-col")
  const districtOptions = form.querySelector("[data-district-options-list]")
  const districtLabel = form.querySelector("[data-filter-district-label]")
  const amenitiesScope = form.querySelector(".filter-amenities-col")
  const priceScope = form.querySelector(".filter-price-col")
  const priceSlider = priceScope?.querySelector("[data-price-slider]")
  const priceMinRange = priceSlider?.querySelector("[data-price-min-range]")
  const priceMaxRange = priceSlider?.querySelector("[data-price-max-range]")
  const priceMinInput = priceScope?.querySelector("[data-price-min-input]")
  const priceMaxInput = priceScope?.querySelector("[data-price-max-input]")
  const priceFill = priceSlider?.querySelector("[data-price-fill]")
  const priceMinLabel = priceSlider?.querySelector("[data-price-min-label]")
  const priceMaxLabel = priceSlider?.querySelector("[data-price-max-label]")

  const closeScopes = (except = null) => {
    scopes.forEach((scope) => {
      const panel = scope.querySelector("[data-filter-panel]")
      const trigger = scope.querySelector("[data-filter-trigger]")
      if (!panel || scope === except) return
      panel.hidden = true
      trigger?.setAttribute("aria-expanded", "false")
    })
  }
  const updateDistrictLabel = () => {
    if (!districtOptions || !districtLabel) return
    const selected = districtOptions.querySelectorAll('input[name="district"]:checked')
    districtLabel.textContent = selected.length ? `${selected.length} ${selected.length === 1 ? form.dataset.districtSingular : form.dataset.districtPlural}` : form.dataset.districtPlural
  }
  const updateAmenitiesLabel = () => {
    const label = amenitiesScope?.querySelector(".filter-label")
    const count = amenitiesScope?.querySelectorAll('input[name="amenities"]:checked').length || 0
    if (label) label.textContent = count ? `${count} ${count === 1 ? form.dataset.amenitySingular : form.dataset.amenityPlural}` : form.dataset.amenitiesLabel
  }
  const formatPrice = (value) => {
    const currency = priceSlider?.dataset.priceCurrency || document.documentElement.dataset.currency || "USD"
    return `${currency} ${new Intl.NumberFormat(document.documentElement.lang || "es", { maximumFractionDigits: 0 }).format(value)}`
  }
  const syncPriceSlider = (changed = null) => {
    if (!priceSlider || !priceMinRange || !priceMaxRange) return
    const floor = Number(priceSlider.dataset.priceFloor)
    const ceiling = Number(priceSlider.dataset.priceCeiling)
    let min = Number(priceMinRange.value)
    let max = Number(priceMaxRange.value)
    if (min > max) {
      if (changed === "min") max = min
      else min = max
      priceMinRange.value = String(min)
      priceMaxRange.value = String(max)
    }
    const span = Math.max(ceiling - floor, 1)
    if (priceFill) {
      priceFill.style.left = `${((min - floor) / span) * 100}%`
      priceFill.style.width = `${((max - min) / span) * 100}%`
    }
    if (priceMinLabel) priceMinLabel.value = formatPrice(min)
    if (priceMaxLabel) priceMaxLabel.value = formatPrice(max)


    if (priceMinInput) priceMinInput.value = min === floor ? "" : String(min)
    if (priceMaxInput) priceMaxInput.value = max === ceiling ? "" : String(max)
  }
  const updatePriceLabel = () => {
    const label = priceScope?.querySelector("[data-price-label]")
    if (!label || !priceMinRange || !priceMaxRange) return
    label.textContent = `${formatPrice(Number(priceMinRange.value))} - ${formatPrice(Number(priceMaxRange.value))}`
  }
  const loadDistricts = async ({ reset = false } = {}) => {
    if (!districtOptions) return
    const previouslySelected = new Set(
      Array.from(districtOptions.querySelectorAll('input[name="district"]:checked')).map((input) => input.value),
    )
    if (reset) previouslySelected.clear()
    districtOptions.replaceChildren()
    if (!cityInput?.value) {
      const empty = document.createElement("p")
      empty.className = "district-empty"
      empty.textContent = form.dataset.selectCityLabel
      districtOptions.append(empty)
      updateDistrictLabel()
      return
    }
    const destinationId = cityInput.value
    const response = await fetch(`/api/locations/districts/?destination=${encodeURIComponent(destinationId)}`)
    if (!response.ok) return
    const data = await response.json()
    if (cityInput.value !== destinationId) return
    if (!data.districts.length) {
      const empty = document.createElement("p")
      empty.className = "district-empty"
      empty.textContent = form.dataset.noDistrictsLabel
      districtOptions.append(empty)
    }
    data.districts.forEach((district, index) => {
      const label = document.createElement("label")
      label.className = "district-check-label"
      const input = document.createElement("input")
      input.type = "checkbox"
      input.name = "district"
      input.value = district.name
      input.id = `results-district-${destinationId}-${index}`
      input.checked = previouslySelected.has(district.name)
      const text = document.createElement("span")
      text.textContent = district.name.toUpperCase()
      label.append(input, text)
      districtOptions.append(label)
    })
    updateDistrictLabel()
  }

  scopes.forEach((scope) => {
    const trigger = scope.querySelector("[data-filter-trigger]")
    const panel = scope.querySelector("[data-filter-panel]")
    if (!trigger || !panel) return
    trigger.setAttribute("aria-expanded", "false")
    trigger.addEventListener("click", (event) => {
      event.stopPropagation()
      const open = panel.hidden
      closeScopes(scope)
      panel.hidden = !open
      trigger.setAttribute("aria-expanded", String(open))
    })
    panel.addEventListener("click", (event) => {
      event.stopPropagation()
      const option = event.target.closest("[data-select-city]")
      if (option && cityInput && countryInput && cityLabel) {
        cityInput.value = option.dataset.id
        countryInput.value = option.dataset.country
        cityLabel.textContent = `${option.dataset.name}, ${option.dataset.countryLabel}`
        closeScopes()
        loadDistricts({ reset: true })
        form.dispatchEvent(new Event("change", { bubbles: true }))
        return
      }
    })
  })
  priceMinRange?.addEventListener("input", () => {
    syncPriceSlider("min")
    updatePriceLabel()
  })
  priceMaxRange?.addEventListener("input", () => {
    syncPriceSlider("max")
    updatePriceLabel()
  })
  form.addEventListener("change", (event) => {
    if (event.target.matches('input[name="district"]')) updateDistrictLabel()
    if (event.target.matches('input[name="amenities"]')) updateAmenitiesLabel()
  })
  document.addEventListener("click", () => closeScopes())

  if (cityInput?.value) loadDistricts()
  else if (districtOptions) loadDistricts()
  updateDistrictLabel()
  updateAmenitiesLabel()
  syncPriceSlider()
  updatePriceLabel()
})



document.querySelectorAll("[data-results-filters]").forEach((form) => {
  const content = document.querySelector("[data-results-content]")
  if (!content) return
  let timer
  let controller

  const updateResults = async (url = null) => {
    const query = url
      ? new URLSearchParams(new URL(url, window.location.origin).searchParams)
      : new URLSearchParams(new FormData(form))
    for (const [key, value] of [...query.entries()]) {
      if (!value && !["check_in", "check_out"].includes(key)) query.delete(key)
    }
    query.set("partial", "1")
    if (!url) query.delete("page")
    if (controller) controller.abort()
    controller = new AbortController()
    try {
      const response = await fetch(`${form.action}?${query.toString()}`, { signal: controller.signal })
      if (!response.ok) return
      content.innerHTML = await response.text()
      query.delete("partial")
      history.replaceState({}, "", `${form.action}?${query.toString()}`)
      if (typeof window.updateResultsMap === "function") {
        window.updateResultsMap()
      }
    } catch (error) {
      if (error.name !== "AbortError") throw error
    }
  }

  form.addEventListener("submit", (event) => {
    event.preventDefault()
    updateResults()
  })
  form.addEventListener("change", () => updateResults())
  form.querySelectorAll("[data-date-range]").forEach((picker) => {
    picker.addEventListener("daterangechange", () => {
      const start = picker.querySelector('[name="check_in"]')
      const end = picker.querySelector('[name="check_out"]')
      if (start && end && Boolean(start.value) === Boolean(end.value)) updateResults()
    })
  })
  form.addEventListener("input", (event) => {
    if (!event.target.matches('input[type="number"], input[type="date"]')) return
    clearTimeout(timer)
    timer = setTimeout(updateResults, 300)
  })
  content.addEventListener("click", (event) => {
    const link = event.target.closest(".results-pager a")
    if (!link) return
    event.preventDefault()
    updateResults(link.href)
  })
})


const pad = (value) => String(value).padStart(2, "0")
const isoFromDate = (date) => `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
const dateFromIso = (iso) => {
  const [year, month, day] = (iso || "").split("-").map(Number)
  return year && month && day ? new Date(year, month - 1, day) : null
}
const sameDay = (a, b) => Boolean(a && b) && a.getTime() === b.getTime()
const startOfMonth = (date) => new Date(date.getFullYear(), date.getMonth(), 1)
const shiftMonth = (date, amount) => new Date(date.getFullYear(), date.getMonth() + amount, 1)
const capitalize = (text) => text.charAt(0).toUpperCase() + text.slice(1)

const rangeLocale = document.documentElement.lang || "es"
const monthFormatter = new Intl.DateTimeFormat(rangeLocale, { month: "short", year: "numeric" })
const monthOnlyFormatter = new Intl.DateTimeFormat(rangeLocale, { month: "short" })
const shortDayFormatter = new Intl.DateTimeFormat(rangeLocale, { day: "2-digit", month: "short", year: "numeric" })
const numericDayFormatter = new Intl.DateTimeFormat(rangeLocale, { day: "2-digit", month: "2-digit", year: "numeric" })
const weekdayFormatter = new Intl.DateTimeFormat(rangeLocale, { weekday: "short" })
const weekdayLabels = Array.from({ length: 7 }, (_, index) => {
  const sunday = new Date(2024, 8, 1)
  const day = new Date(sunday)
  day.setDate(sunday.getDate() + index)
  return capitalize(weekdayFormatter.format(day).replace(/\.$/, ""))
})

const rangeToday = dateFromIso(document.documentElement.dataset.today) || new Date()
rangeToday.setHours(0, 0, 0, 0)

document.querySelectorAll("[data-date-range]").forEach((picker) => {
  const trigger = picker.querySelector("[data-date-trigger]")
  const summary = picker.querySelector("[data-date-summary]")
  const singleDate = picker.dataset.dateSingle === "true"
  const birthdayPicker = singleDate && picker.dataset.allowPast === "true"
  const startName = picker.dataset.dateStart || "check_in"
  const endName = picker.dataset.dateEnd || "check_out"
  const startInput = picker.querySelector(`input[name="${startName}"]`)
  const endInput = singleDate ? null : picker.querySelector(`input[name="${endName}"]`)
  if (!trigger || !startInput || (!singleDate && !endInput)) return

  let start = dateFromIso(startInput.value)
  let end = endInput ? dateFromIso(endInput.value) : null
  let view = startOfMonth(start || rangeToday)
  const isHeroDatePicker = Boolean(picker.closest(".home-search"))
  const isEnglish = rangeLocale.toLowerCase().startsWith("en")
  const minAllowed = dateFromIso(picker.dataset.minDate) || (picker.dataset.allowPast === "true" ? new Date(1900, 0, 1) : rangeToday)
  const maxAllowed = dateFromIso(picker.dataset.maxDate) || (picker.dataset.allowPast === "true" ? rangeToday : null)
  if (start && (start < minAllowed || (maxAllowed && start > maxAllowed))) start = null
  if (end && (!start || end <= start || end < minAllowed || (maxAllowed && end > maxAllowed))) end = null

  const panel = document.createElement("div")
  panel.className = "date-panel"
  if (singleDate) panel.classList.add("date-panel-single")
  if (birthdayPicker) panel.classList.add("date-panel-birthday")
  panel.setAttribute("role", "dialog")
  panel.setAttribute("aria-label", summary ? summary.dataset.empty : (isEnglish ? "Dates" : "Fechas"))
  panel.hidden = true
  panel.innerHTML =
    '<div class="date-panel-head">' +
    `<button type="button" class="date-nav" data-nav="-1" aria-label="${isEnglish ? "Previous month" : "Mes anterior"}">\u2039</button>` +
    '<div class="date-months" data-months></div>' +
    `<button type="button" class="date-nav" data-nav="1" aria-label="${isEnglish ? "Next month" : "Mes siguiente"}">\u203A</button>` +
    "</div>" +
    `<button type="button" class="date-clear" data-clear>${isEnglish ? "Clear selection" : "Quitar selección"}</button>`



  document.body.appendChild(panel)
  if (isHeroDatePicker) panel.classList.add("hero-date-panel")

  const monthsEl = panel.querySelector("[data-months]")

  const positionPanel = () => {
    const rect = picker.getBoundingClientRect()
    const width = panel.offsetWidth
    const height = panel.offsetHeight
    const margin = 12
    let left = rect.left + rect.width / 2 - width / 2
    left = Math.min(left, window.innerWidth - width - margin)
    left = Math.max(margin, left)
    let top = rect.bottom + margin



    if (!isHeroDatePicker && top + height > window.innerHeight - margin && rect.top - height - margin > margin) {
      top = rect.top - height - margin
    }
    panel.style.left = `${left + (isHeroDatePicker ? window.scrollX : 0)}px`
    panel.style.top = `${top + (isHeroDatePicker ? window.scrollY : 0)}px`
    panel.style.maxHeight = isHeroDatePicker ? "" : `${Math.max(180, window.innerHeight - top - margin)}px`
  }

  const monthMarkup = (monthDate) => {
    const year = monthDate.getFullYear()
    const month = monthDate.getMonth()
    const offset = new Date(year, month, 1).getDay()
    const days = new Date(year, month + 1, 0).getDate()
    let cells = ""
    for (let i = 0; i < offset; i += 1) cells += '<span class="date-cell is-empty"></span>'
    for (let day = 1; day <= days; day += 1) {
      const date = new Date(year, month, day)
      const classes = ["date-cell"]
      if (sameDay(date, start) || sameDay(date, end)) classes.push("is-selected")
      else if (start && end && date > start && date < end) classes.push("is-in-range")
      const selectingStart = singleDate || !start || Boolean(start && end)
      const disabled = date < minAllowed || (maxAllowed && date > maxAllowed) || (!singleDate && selectingStart && maxAllowed && date >= maxAllowed)
      if (disabled) classes.push("is-disabled")
      cells += `<button type="button" class="${classes.join(" ")}" data-date="${isoFromDate(date)}"${disabled ? " disabled" : ""}>${day}</button>`
    }
    const weekdays = weekdayLabels.map((label) => `<span class="date-weekday">${label}</span>`).join("")
    const yearControl = birthdayPicker
      ? `<select class="date-year-select" data-date-year aria-label="${picker.dataset.yearLabel || "Year"}">${Array.from(
          { length: maxAllowed.getFullYear() - minAllowed.getFullYear() + 1 },
          (_, index) => maxAllowed.getFullYear() - index,
        )
          .map((optionYear) => `<option value="${optionYear}"${optionYear === year ? " selected" : ""}>${optionYear}</option>`)
          .join("")}</select>`
      : ""
    const monthLabel = birthdayPicker ? monthOnlyFormatter.format(monthDate) : monthFormatter.format(monthDate)
    return (
      '<div class="date-month">' +
      `<div class="date-month-heading"><p class="date-month-label">${capitalize(monthLabel)}</p>${yearControl}</div>` +
      `<div class="date-grid">${weekdays}${cells}</div>` +
      "</div>"
    )
  }

  const render = () => {
    monthsEl.innerHTML = monthMarkup(view) + (singleDate ? "" : monthMarkup(shiftMonth(view, 1)))
    if (!summary) return
    if (start && end) summary.textContent = `${shortDayFormatter.format(start)} - ${shortDayFormatter.format(end)}`
    else if (start) summary.textContent = picker.dataset.dateFormat === "numeric"
      ? numericDayFormatter.format(start)
      : shortDayFormatter.format(start)
    else summary.textContent = summary.dataset.empty || ""
  }

  const syncInputs = () => {
    startInput.value = start ? isoFromDate(start) : ""
    if (endInput) endInput.value = end ? isoFromDate(end) : ""
  }

  const open = () => {
    panel.hidden = false
    trigger.setAttribute("aria-expanded", "true")
    const updateButton = picker.closest("[data-reservation-edit]")?.querySelector(".svc-stay-update")
    if (updateButton) updateButton.hidden = false
    render()
    positionPanel()
  }
  const close = () => {
    panel.hidden = true
    trigger.setAttribute("aria-expanded", "false")
  }

  trigger.addEventListener("click", (event) => {
    event.stopPropagation()
    panel.hidden ? open() : close()
  })

  panel.addEventListener("click", (event) => {
    event.stopPropagation()
    const nav = event.target.closest("[data-nav]")
    if (nav) {
      const target = shiftMonth(view, Number(nav.dataset.nav))
      if (target >= startOfMonth(minAllowed) && (!maxAllowed || target <= startOfMonth(maxAllowed))) {
        view = target
        render()
      }
      return
    }
    if (event.target.closest("[data-clear]")) {
      start = null
      end = null
      syncInputs()
      render()
      picker.dispatchEvent(new Event("daterangechange"))
      return
    }
    const cell = event.target.closest("[data-date]")
    if (!cell) return
    const date = dateFromIso(cell.dataset.date)
    if (singleDate) {
      start = date
      syncInputs()
      render()
      picker.dispatchEvent(new Event("daterangechange"))
      close()
      return
    }
    let completedRange = false
    if (!start || (start && end)) {
      start = date
      end = null
    } else if (date > start) {
      end = date
      completedRange = true
    } else {
      start = date
    }
    syncInputs()
    render()
    picker.dispatchEvent(new Event("daterangechange"))
    if (completedRange) close()
  })

  panel.addEventListener("change", (event) => {
    const yearSelect = event.target.closest("[data-date-year]")
    if (!yearSelect) return
    const year = Number(yearSelect.value)
    let month = view.getMonth()
    if (year === minAllowed.getFullYear() && month < minAllowed.getMonth()) month = minAllowed.getMonth()
    if (year === maxAllowed.getFullYear() && month > maxAllowed.getMonth()) month = maxAllowed.getMonth()
    view = new Date(year, month, 1)
    render()
  })

  document.addEventListener("click", (event) => {
    if (!picker.contains(event.target) && !panel.contains(event.target)) close()
  })

  picker.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      close()
      trigger.focus()
    }
  })

  syncInputs()
  render()
})



document.querySelectorAll("[data-booking-quote]").forEach((booking) => {
  const start = booking.querySelector('input[name="check_in"]')
  const end = booking.querySelector('input[name="check_out"]')
  const summary = booking.querySelector("[data-booking-summary]")
  const nightlyRate = Number(booking.dataset.nightlyRate)
  const monthlyRate = Number(booking.dataset.monthlyRate)
  const currency = booking.dataset.currency || "USD"
  if (!start || !end || !summary || !Number.isFinite(nightlyRate)) return


  const card = booking.closest("[data-booking-card]")
  const typeInput = card ? card.querySelector("[data-booking-type-input]") : null
  const dailyForm = card ? card.querySelector("[data-booking-daily-form]") : null
  const monthlyForm = card ? card.querySelector("[data-booking-monthly-form]") : null
  let activeType = (typeInput && typeInput.value) || "daily"

  const fmt = (value) =>
    new Intl.NumberFormat(document.documentElement.lang || "es", {
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(Math.round(value))

  const updateQuote = () => {
    const checkIn = dateFromIso(start.value)
    const checkOut = dateFromIso(end.value)
    if (!checkIn || !checkOut || checkOut <= checkIn) {
      summary.textContent = ""
      return
    }
    const nights = Math.round((checkOut - checkIn) / 86400000)
    let amount
    if (activeType === "monthly" && Number.isFinite(monthlyRate)) {

      amount = fmt((monthlyRate / 30) * nights)
    } else {
      amount = fmt(nightlyRate * nights)
    }
    const language = document.documentElement.lang.toLowerCase().startsWith("en") ? "en" : "es"
    const nightLabel = new Intl.NumberFormat(language).format(nights)
    const nightText = nights === 1 ? (language === "en" ? "night" : "noche") : (language === "en" ? "nights" : "noches")
    summary.textContent = `${nightLabel} ${nightText} · ${currency} ${amount}`
  }


  if (card) {
    const tabs = card.querySelectorAll("[data-booking-tab]")
    const rateDaily = card.querySelector("[data-rate-daily]")
    const rateMonthly = card.querySelector("[data-rate-monthly]")
    tabs.forEach((tab) => {
      tab.addEventListener("click", () => {
        tabs.forEach((t) => t.classList.remove("active"))
        tab.classList.add("active")
        activeType = tab.dataset.bookingTab
        if (typeInput) typeInput.value = activeType
        if (rateDaily) rateDaily.hidden = activeType !== "daily"
        if (rateMonthly) rateMonthly.hidden = activeType !== "monthly"
        if (dailyForm) dailyForm.hidden = activeType === "monthly"
        if (monthlyForm) monthlyForm.hidden = activeType !== "monthly"
        updateQuote()
      })
    })
  }

  booking.addEventListener("daterangechange", updateQuote)
  updateQuote()
})

document.querySelectorAll("[data-booking-daily-form], [data-booking-monthly-form]").forEach((form) => {
  const errorsBox = form.querySelector("[data-booking-errors]")
  if (!errorsBox) return

  const getErrors = () => {
    const errors = []
    const email = form.querySelector('[name="email"]')
    const phone = form.querySelector('[name="phone"]')
    const name = form.querySelector('[name="full_name"]')
    const checkIn = form.querySelector('[name="check_in"]')
    const checkOut = form.querySelector('[name="check_out"]')
    const emailValue = email ? email.value.trim() : ""
    const phoneValue = phone ? phone.value.trim() : ""

    if (name && !name.value.trim()) errors.push(errorsBox.dataset.nameMissing)
    if (!emailValue) errors.push(errorsBox.dataset.emailMissing)
    else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(emailValue)) errors.push(errorsBox.dataset.emailInvalid)
    if (!phoneValue) errors.push(errorsBox.dataset.phoneMissing)
    else if (!/^[\d\s().-]{6,}$/.test(phoneValue) || phoneValue.replace(/\D/g, "").length < 6) {
      errors.push(errorsBox.dataset.phoneInvalid)
    }
    if (checkIn && !checkIn.value) errors.push(errorsBox.dataset.checkInMissing)
    if (checkOut && !checkOut.value) errors.push(errorsBox.dataset.checkOutMissing)
    else if (checkIn && checkIn.value && checkOut.value <= checkIn.value) errors.push(errorsBox.dataset.dateOrderInvalid)
    return errors.filter(Boolean)
  }

  form.addEventListener("submit", (event) => {
    const errors = getErrors()
    if (!errors.length) {
      errorsBox.hidden = true
      errorsBox.textContent = ""
      return
    }
    event.preventDefault()
    errorsBox.textContent = errors.join("\n")
    errorsBox.hidden = false
    const firstEmpty = [...form.querySelectorAll("input")].find((input) => !input.value.trim() && input.type !== "hidden")
    if (firstEmpty) firstEmpty.focus()
    else if (form.querySelector('[name="check_in"]') && !form.querySelector('[name="check_in"]').value) {
      form.querySelector("[data-date-trigger]")?.focus()
    }
  })

  form.addEventListener("input", () => {
    if (errorsBox.hidden || getErrors().length) return
    errorsBox.hidden = true
    errorsBox.textContent = ""
  })
})


document.querySelectorAll("[data-guest-picker]").forEach((picker) => {
  const trigger = picker.querySelector("[data-guest-trigger]")
  const panel = picker.querySelector("[data-guest-panel]")
  const input = picker.querySelector("[data-guest-input]")
  const counter = picker.querySelector("[data-guest-count]")
  const label = picker.querySelector("[data-guest-label]")
  if (!trigger || !panel || !input || !counter || !label) return

  const MIN_GUESTS = 1
  const MAX_GUESTS = 20

  const close = () => {
    panel.hidden = true
    trigger.setAttribute("aria-expanded", "false")
  }

  trigger.addEventListener("click", () => {
    const open = panel.hidden
    panel.hidden = !open
    trigger.setAttribute("aria-expanded", String(open))
  })

  picker.querySelectorAll("[data-guest-step]").forEach((button) => {
    button.addEventListener("click", () => {
      const total = Number(input.value) + Number(button.dataset.guestStep)
      const guests = Math.min(MAX_GUESTS, Math.max(MIN_GUESTS, total))
      input.value = String(guests)
      counter.textContent = String(guests)
      const isEnglish = document.documentElement.lang.toLowerCase().startsWith("en")
      label.textContent = isEnglish
        ? `${guests} ${guests === 1 ? "guest" : "guests"}`
        : `${guests} ${guests === 1 ? "huésped" : "huéspedes"}`
    })
  })

  document.addEventListener("click", (event) => {
    if (!picker.contains(event.target)) close()
  })

  picker.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      close()
      trigger.focus()
    }
  })
})



const registroForm = document.querySelector("[data-registro-form]")

if (registroForm) {
  const PASSWORD_MIN_LENGTH = 10
  const NAME_TOKEN_MIN_LENGTH = 3
  const PASSWORD_SYMBOLS = "!\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~"
  const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

  const passwordInput = registroForm.querySelector("[data-password-input]")
  const rulesList = registroForm.querySelector("[data-password-rules]")
  const strengthLabel = registroForm.querySelector("[data-strength-label]")
  const emailInput = registroForm.querySelector('[name="email"]')
  const fullNameInput = registroForm.querySelector('[name="full_name"]')
  const toggleButton = registroForm.querySelector("[data-password-toggle]")
  const requiredInputs = Array.from(registroForm.querySelectorAll("[data-required]"))
  const watched = passwordInput ? [...requiredInputs, passwordInput] : requiredInputs
  const touched = new Set()

  const passwordIssues = (password) => {
    const value = password || ""
    const emailUser = emailInput ? (emailInput.value.split("@")[0] || "") : ""
    const source = `${fullNameInput ? fullNameInput.value : ""} ${emailUser}`.toLowerCase()
    const tokens = source.split(/[\s._-]+/).filter((token) => token.length >= NAME_TOKEN_MIN_LENGTH)
    const hasSymbol = Array.from(value).some((character) => /[0-9]/.test(character) || PASSWORD_SYMBOLS.includes(character))
    const issues = []
    if (value.length < PASSWORD_MIN_LENGTH) issues.push("length")
    if (!hasSymbol) issues.push("symbol")
    if (tokens.some((token) => value.toLowerCase().includes(token))) issues.push("name")
    if (issues.length) issues.push("strength")
    return issues
  }

  const isValid = (input) => {
    const value = (input.value || "").trim()
    if (input === emailInput) return EMAIL_PATTERN.test(value)
    if (input.name === "phone") return /^[\d\s().-]{6,}$/.test(value) && value.replace(/\D/g, "").length >= 6
    return value.length > 0
  }

  const render = () => {
    let valid = true

    watched.forEach((input) => {
      const filled = isValid(input)
      if (!filled) valid = false
      const field = input.closest(".registro-field")
      if (field) {
        const hasServerError = Boolean(field.querySelector(".registro-error")) && !touched.has(input)
        field.classList.toggle("is-invalid", hasServerError || (!filled && touched.has(input)))
      }
    })

    if (passwordInput && rulesList) {
      const value = passwordInput.value
      const issues = passwordIssues(value)
      const showRules = touched.has(passwordInput) || value.length > 0
      rulesList.hidden = !showRules
      if (showRules) {
        const empty = value.length === 0
        rulesList.querySelectorAll("[data-rule]").forEach((item) => {
          item.classList.toggle("is-error", empty || issues.includes(item.dataset.rule))
        })
        if (strengthLabel) {
          strengthLabel.textContent = issues.length ? rulesList.dataset.labelWeak : rulesList.dataset.labelStrong
        }
      }
      const passwordField = passwordInput.closest(".registro-field")
      if (issues.length) {
        valid = false
        if (passwordField && touched.has(passwordInput)) {
          passwordField.classList.add("is-invalid")
        }
      } else if (passwordField && touched.has(passwordInput) && !passwordField.querySelector(".registro-error")) {
        passwordField.classList.remove("is-invalid")
      }
    }

    if (toggleButton && passwordInput) toggleButton.hidden = passwordInput.value.length === 0
    return valid
  }

  watched.forEach((input) => {
    input.addEventListener("input", render)
    input.addEventListener("change", render)
    input.addEventListener("blur", () => {
      touched.add(input)
      render()
    })
  })

  registroForm.addEventListener("submit", (event) => {
    watched.forEach((input) => touched.add(input))
    if (passwordInput) touched.add(passwordInput)
    const valid = render()
    if (!valid) {
      event.preventDefault()
      const firstInvalid = registroForm.querySelector(".registro-field.is-invalid input, .registro-field.is-invalid select")
      if (firstInvalid) {
        firstInvalid.focus()
        firstInvalid.scrollIntoView({ behavior: "smooth", block: "center" })
      }
    }
  })


  registroForm.querySelectorAll(".registro-field.is-invalid input, .registro-field.is-invalid select").forEach((input) => {
    touched.add(input)
  })
  if (rulesList && !rulesList.hidden && passwordInput) touched.add(passwordInput)


  const checkoutDates = document.querySelector("[data-checkout-dates]")
  if (checkoutDates) {
    const hiddenCheckIn = registroForm.querySelector('input[name="check_in"]')
    const hiddenCheckOut = registroForm.querySelector('input[name="check_out"]')
    const pickerCheckIn = checkoutDates.querySelector('input[name="check_in"]')
    const pickerCheckOut = checkoutDates.querySelector('input[name="check_out"]')
    const rateLabel = document.querySelector("[data-line-rate-label]")
    const subtotalEl = document.querySelector("[data-line-subtotal]")
    const totalEl = document.querySelector("[data-line-total]")
    const pointsEl = document.querySelector("[data-line-points]")
    const serviceLinesEl = document.querySelector("[data-service-lines]")

    const nightlyRate = Number(checkoutDates.dataset.nightlyRate) || 0
    const cleaningFee = Number(checkoutDates.dataset.cleaningFee) || 0
    const currency = checkoutDates.dataset.currency || "$"
    const serviceButtons = Array.from(registroForm.querySelectorAll("[data-service-add]"))
    const renderTotal = (baseTotal, nights) => {
      let servicesTotal = 0
      if (serviceLinesEl) serviceLinesEl.replaceChildren()

      serviceButtons.forEach((button) => {
        const key = button.dataset.serviceKey
        const selected = Array.from(registroForm.querySelectorAll('input[name="selected_services"]'))
          .some((input) => input.value === key)
        if (!selected) return
        const unitPrice = Number(button.dataset.servicePrice) || 0
        const amount = unitPrice * (button.dataset.serviceUnit === "night" ? nights : 1)
        servicesTotal += amount

        if (serviceLinesEl) {
          const line = document.createElement("div")
          const label = document.createElement("span")
          const price = document.createElement("span")
          label.textContent = button.dataset.serviceLabel || button.textContent.trim()
          price.textContent = `${currency} ${Number((amount).toFixed(2))}`
          line.append(label, price)
          serviceLinesEl.appendChild(line)
        }
      })

      if (serviceLinesEl) serviceLinesEl.hidden = servicesTotal === 0
      const total = baseTotal + servicesTotal
      const pointsRate = Number(pointsEl && pointsEl.dataset.pointsRate) || 0
      if (totalEl) totalEl.textContent = `${currency} ${Number((total).toFixed(2))}`
      if (pointsEl) pointsEl.textContent = `${Math.max(0, Math.round(total * pointsRate))} Wynwood Points`
    }

    const updateStaySummary = () => {
      if (pickerCheckIn && hiddenCheckIn) hiddenCheckIn.value = pickerCheckIn.value
      if (pickerCheckOut && hiddenCheckOut) hiddenCheckOut.value = pickerCheckOut.value

      const start = dateFromIso(pickerCheckIn ? pickerCheckIn.value : "")
      const end = dateFromIso(pickerCheckOut ? pickerCheckOut.value : "")
      if (!start || !end || end <= start) return

      const nights = Math.max(1, Math.round((end - start) / 86400000))
      const subtotal = nightlyRate * nights
      const total = subtotal + cleaningFee

      if (rateLabel) rateLabel.textContent = `${currency} ${Number((nightlyRate).toFixed(2))} x ${nights}`
      if (subtotalEl) subtotalEl.textContent = `${currency} ${Number((subtotal).toFixed(2))}`
      renderTotal(total, nights)
    }

    checkoutDates.addEventListener("daterangechange", updateStaySummary)

    serviceButtons.forEach((button) => {
      const key = button.dataset.serviceKey
      button.addEventListener("click", () => {
        if (!render()) {
          watched.forEach((input) => touched.add(input))
          render()
          const firstInvalid = registroForm.querySelector(".registro-field.is-invalid input, .registro-field.is-invalid select")
          if (firstInvalid) {
            firstInvalid.focus()
            firstInvalid.scrollIntoView({ behavior: "smooth", block: "center" })
          }
          return
        }
        const added = button.classList.toggle("is-added")
        button.textContent = added ? button.dataset.labelAdded : `+ ${button.dataset.labelAdd}`
        button.setAttribute("aria-pressed", String(added))
        if (key) {
          let input = registroForm.querySelector(`input[name="selected_services"][value="${key}"]`)
          if (added && !input) {
            input = document.createElement("input")
            input.type = "hidden"
            input.name = "selected_services"
            input.value = key
            registroForm.appendChild(input)
          } else if (!added && input) {
            input.remove()
          }
        }
        const start = dateFromIso(hiddenCheckIn ? hiddenCheckIn.value : "")
        const end = dateFromIso(hiddenCheckOut ? hiddenCheckOut.value : "")
        const nights = start && end && end > start ? Math.max(1, Math.round((end - start) / 86400000)) : 1
        renderTotal(nightlyRate * nights + cleaningFee, nights)

      })
    })

    updateStaySummary()
  }

  const checkoutGuestPicker = document.querySelector("[data-checkout-guest-picker]")
  if (checkoutGuestPicker) {
    const trigger = checkoutGuestPicker.querySelector("[data-checkout-guest-trigger]")
    const panel = checkoutGuestPicker.querySelector("[data-checkout-guest-panel]")
    const countEl = checkoutGuestPicker.querySelector("[data-checkout-guest-count]")
    const labelEl = checkoutGuestPicker.querySelector("[data-checkout-guest-label]")
    const hiddenGuests = registroForm.querySelector('input[name="guests"]')
    const maxGuests = Number(checkoutGuestPicker.dataset.maxGuests) || 20

    const togglePanel = () => {
      const isHidden = panel.hidden
      panel.hidden = !isHidden
      trigger.setAttribute("aria-expanded", String(isHidden))
    }

    trigger.addEventListener("click", (event) => {
      event.stopPropagation()
      togglePanel()
    })

    checkoutGuestPicker.querySelectorAll("[data-checkout-guest-step]").forEach((btn) => {
      btn.addEventListener("click", (event) => {
        event.stopPropagation()
        const step = Number(btn.dataset.checkoutGuestStep)
        let current = Number(countEl.textContent) || 1
        current = Math.min(maxGuests, Math.max(1, current + step))
        countEl.textContent = String(current)
        if (labelEl) {
          labelEl.textContent = `${current} ${current === 1 ? checkoutGuestPicker.dataset.personSingular : checkoutGuestPicker.dataset.personPlural}`
        }
        if (hiddenGuests) hiddenGuests.value = String(current)
      })
    })

    document.addEventListener("click", (event) => {
      if (!checkoutGuestPicker.contains(event.target)) {
        panel.hidden = true
        trigger.setAttribute("aria-expanded", "false")
      }
    })
  }

  render()
}

document.querySelectorAll("[data-reservation-guest-picker]").forEach((picker) => {
  const trigger = picker.querySelector("[data-reservation-guest-trigger]")
  const panel = picker.querySelector("[data-reservation-guest-panel]")
  const countEl = picker.querySelector("[data-reservation-guest-count]")
  const labelEl = picker.querySelector("[data-reservation-guest-label]")
  const hiddenGuests = picker.querySelector('input[name="guests"]')
  const maxGuests = Number(picker.dataset.maxGuests) || 1
  const isEnglish = document.documentElement.lang.toLowerCase().startsWith("en")

  trigger.addEventListener("click", (event) => {
    event.stopPropagation()
    panel.hidden = !panel.hidden
    trigger.setAttribute("aria-expanded", String(!panel.hidden))
    const updateButton = picker.closest("[data-reservation-edit]")?.querySelector(".svc-stay-update")
    if (updateButton) updateButton.hidden = false
  })

  picker.querySelectorAll("[data-reservation-guest-step]").forEach((button) => {
    button.addEventListener("click", (event) => {
      event.stopPropagation()
      const current = Number(countEl.textContent) || 1
      const next = Math.min(maxGuests, Math.max(1, current + Number(button.dataset.reservationGuestStep)))
      countEl.textContent = String(next)
      hiddenGuests.value = String(next)
      labelEl.textContent = isEnglish
        ? `${next} ${next === 1 ? "person" : "people"}`
        : `${next} ${next === 1 ? "persona" : "personas"}`
    })
  })

  document.addEventListener("click", (event) => {
    if (!picker.contains(event.target)) {
      panel.hidden = true
      trigger.setAttribute("aria-expanded", "false")
    }
  })
})

document.querySelectorAll("[data-payment-method-picker]").forEach((picker) => {
  const form = picker.parentElement.querySelector("[data-payment-form]")
  const openButton = picker.querySelector("[data-payment-method-open]")
  const changeButton = form && form.querySelector("[data-payment-method-change]")
  if (!form || !openButton || !changeButton) return

  openButton.addEventListener("click", () => {
    picker.hidden = true
    form.hidden = false
    openButton.setAttribute("aria-expanded", "true")
  })

  changeButton.addEventListener("click", () => {
    form.hidden = true
    picker.hidden = false
    openButton.setAttribute("aria-expanded", "false")
  })
})

document.querySelectorAll("[data-payment-form]").forEach((form) => {
  const submit = form.querySelector("[data-payment-submit]")
  if (!submit) return

  const updateSubmit = () => {
    const fields = Array.from(form.querySelectorAll("input[required], select[required], textarea[required]"))
    submit.disabled = fields.some((field) => field.type === "checkbox" ? !field.checked : !field.value.trim())
  }

  form.addEventListener("input", updateSubmit)
  form.addEventListener("change", updateSubmit)
  updateSubmit()
})


document.querySelectorAll("[data-password-toggle]").forEach((toggle) => {
  const input = toggle.parentElement && toggle.parentElement.querySelector("input")
  if (!input) return
  const eyeOpen = toggle.querySelector("[data-eye-open]")
  const eyeClosed = toggle.querySelector("[data-eye-closed]")
  const eyeOn = toggle.querySelector("[data-eye-on]")
  const eyeOff = toggle.querySelector("[data-eye-off]")

  toggle.addEventListener("click", () => {
    const reveal = input.type === "password"
    input.type = reveal ? "text" : "password"
    toggle.setAttribute("aria-pressed", String(reveal))
    toggle.setAttribute("aria-label", reveal ? toggle.dataset.labelHide : toggle.dataset.labelShow)
    if (eyeOff || eyeOn) {
      if (eyeOff) eyeOff.hidden = reveal
      if (eyeOn) eyeOn.hidden = !reveal
    } else {
      if (eyeOpen) eyeOpen.hidden = reveal
      if (eyeClosed) eyeClosed.hidden = !reveal
    }
  })
})


const destinationsSection = document.querySelector(".destinations-section")
if (destinationsSection) {
  const track = destinationsSection.querySelector(".destination-track")
  const prevBtn = destinationsSection.querySelector(".arrow-prev")
  const nextBtn = destinationsSection.querySelector(".arrow-next")

  if (track && prevBtn && nextBtn) {
    const updateArrows = () => {
      const atStart = track.scrollLeft <= 5
      const atEnd = track.scrollLeft + track.clientWidth >= track.scrollWidth - 5

      const prevPath = prevBtn.querySelector("path")
      const nextPath = nextBtn.querySelector("path")

      if (prevPath) prevPath.setAttribute("stroke", atStart ? "#D1D1D1" : "#000000")
      if (nextPath) nextPath.setAttribute("stroke", atEnd ? "#D1D1D1" : "#000000")

      prevBtn.style.cursor = atStart ? "default" : "pointer"
      nextBtn.style.cursor = atEnd ? "default" : "pointer"
      prevBtn.disabled = atStart
      nextBtn.disabled = atEnd
    }

    const getScrollStep = () => {
      const tile = track.querySelector(".destination-tile")
      if (tile) {
        const gap = parseInt(window.getComputedStyle(track).gap, 10) || 12
        return tile.offsetWidth + gap
      }
      return 271
    }

    prevBtn.addEventListener("click", () => {
      track.scrollBy({ left: -getScrollStep(), behavior: "smooth" })
    })

    nextBtn.addEventListener("click", () => {
      track.scrollBy({ left: getScrollStep(), behavior: "smooth" })
    })

    track.addEventListener("scroll", updateArrows, { passive: true })
    window.addEventListener("resize", updateArrows, { passive: true })
    updateArrows()
  }
}


const initPromoCountdown = () => {
  const ribbon = document.querySelector("[data-countdown-ribbon]")
  if (!ribbon) return
  const hoursEl = ribbon.querySelector("[data-countdown-hours]")
  const minutesEl = ribbon.querySelector("[data-countdown-minutes]")
  const secondsEl = ribbon.querySelector("[data-countdown-seconds]")
  if (!hoursEl || !minutesEl || !secondsEl) return

  const updateCountdown = () => {
    const now = new Date()
    const midnight = new Date(now)
    midnight.setHours(24, 0, 0, 0)
    const diff = Math.max(0, midnight - now)

    const hours = Math.floor(diff / (1000 * 60 * 60))
    const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60))
    const seconds = Math.floor((diff % (1000 * 60)) / 1000)

    hoursEl.textContent = String(hours).padStart(2, "0")
    minutesEl.textContent = String(minutes).padStart(2, "0")
    secondsEl.textContent = String(seconds).padStart(2, "0")
  }

  updateCountdown()
  setInterval(updateCountdown, 1000)
}
initPromoCountdown()




;(() => {
  let resultsMapInstance = null
  let markersGroup = null
  const markerById = new Map()

  const initResultsMap = () => {
    const mapEl = document.getElementById("results-map")
    if (!mapEl || !window.L) return

    if (!resultsMapInstance) {
      resultsMapInstance = window.L.map(mapEl, {
        zoomControl: true,
        scrollWheelZoom: false,
      })
      window.L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 19,
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank">OpenStreetMap</a>',
      }).addTo(resultsMapInstance)
      markersGroup = window.L.featureGroup().addTo(resultsMapInstance)
    }

    renderResultsMarkers()
  }

  const renderResultsMarkers = () => {
    if (!resultsMapInstance || !markersGroup || !window.L) return
    const mapEl = document.getElementById("results-map")
    markersGroup.clearLayers()
    markerById.clear()

    const dataEl = document.getElementById("properties-map-data")
    if (!dataEl) return

    let properties = []
    try {
      properties = JSON.parse(dataEl.textContent || "[]")
    } catch {
      properties = []
    }

    if (!Array.isArray(properties) || properties.length === 0) {
      resultsMapInstance.setView([20, 0], 2)
      return
    }

    properties.forEach((prop) => {
      if (typeof prop.lat !== "number" || typeof prop.lng !== "number") return

      const badge = document.createElement("div")
      badge.className = "map-price-badge"
      badge.dataset.markerId = String(prop.id)
      const badgeText = document.createElement("span")
      badgeText.textContent = `${prop.currency} ${Number((prop.price).toFixed(2))}`
      badge.append(badgeText)
      const icon = window.L.divIcon({
        html: badge,
        className: "map-custom-marker-icon",
        iconSize: [80, 32],
        iconAnchor: [40, 16],
        popupAnchor: [0, -18],
      })

      const marker = window.L.marker([prop.lat, prop.lng], { icon: icon })

      const popup = document.createElement("div")
      popup.className = "map-popup-card"
      if (prop.image) {
        const image = document.createElement("img")
        image.src = prop.image
        image.alt = prop.title
        popup.append(image)
      }
      const heading = document.createElement("h4")
      heading.textContent = prop.title
      const location = document.createElement("p")
      location.textContent = `${prop.district ? `${prop.district}, ` : ""}${prop.destination}`
      const price = document.createElement("strong")
      price.textContent = `${prop.currency} ${Number((prop.price).toFixed(2))} / ${mapEl.dataset.nightLabel}`
      const linkWrapper = document.createElement("div")
      const link = document.createElement("a")
      link.href = prop.url
      link.textContent = mapEl.dataset.viewProperty
      linkWrapper.append(link)
      popup.append(heading, location, price, linkWrapper)
      marker.bindPopup(popup)

      marker.on("click", () => {
        const card = document.querySelector(`.result-card[data-property-id="${prop.id}"]`)
        if (card) {
          document.querySelectorAll(".result-card.is-highlighted").forEach((c) => c.classList.remove("is-highlighted"))
          card.classList.add("is-highlighted")
          card.scrollIntoView({ behavior: "smooth", block: "nearest" })
        }
      })

      markersGroup.addLayer(marker)
      markerById.set(String(prop.id), marker)
    })

    const bounds = markersGroup.getBounds()
    if (bounds.isValid()) {
      resultsMapInstance.fitBounds(bounds.pad(0.15), { maxZoom: 14 })
    }

    document.querySelectorAll(".result-card[data-property-id]").forEach((card) => {
      const propId = card.getAttribute("data-property-id")
      card.addEventListener("mouseenter", () => {
        const marker = markerById.get(String(propId))
        if (marker) {
          const el = marker.getElement()
          if (el) {
            const badge = el.querySelector(".map-price-badge")
            if (badge) badge.classList.add("is-active")
          }
        }
      })
      card.addEventListener("mouseleave", () => {
        const marker = markerById.get(String(propId))
        if (marker) {
          const el = marker.getElement()
          if (el) {
            const badge = el.querySelector(".map-price-badge")
            if (badge) badge.classList.remove("is-active")
          }
        }
      })
    })

    setTimeout(() => {
      if (resultsMapInstance) resultsMapInstance.invalidateSize()
    }, 200)
  }

  window.updateResultsMap = renderResultsMarkers

  const initDetailMap = () => {
    const detailMapEl = document.getElementById("detail-map")
    if (!detailMapEl || !window.L) return

    const lat = parseFloat(detailMapEl.dataset.lat)
    const lng = parseFloat(detailMapEl.dataset.lng)
    if (isNaN(lat) || isNaN(lng)) return

    const map = window.L.map(detailMapEl, {
      zoomControl: true,
      scrollWheelZoom: false,
    }).setView([lat, lng], 14)

    window.L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank">OpenStreetMap</a>',
    }).addTo(map)

    const title = detailMapEl.dataset.title || ""
    const price = detailMapEl.dataset.price || ""
    const currency = detailMapEl.dataset.currency || ""

    const badgeHtml = `<div class="map-price-badge is-active"><span>${currency} ${price}</span></div>`
    const icon = window.L.divIcon({
      html: badgeHtml,
      className: "map-custom-marker-icon",
      iconSize: [80, 32],
      iconAnchor: [40, 16],
    })

    const marker = window.L.marker([lat, lng], { icon: icon }).addTo(map)
    if (title) {
      const tooltip = document.createElement("span")
      tooltip.textContent = title
      marker.bindTooltip(tooltip, { permanent: false, direction: "top" })
    }

    setTimeout(() => map.invalidateSize(), 200)
  }

  const startMaps = () => {
    if (window.L) {
      initResultsMap()
      initDetailMap()
    } else {
      window.addEventListener("load", () => {
        if (window.L) {
          initResultsMap()
          initDetailMap()
        }
      })
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", startMaps)
  } else {
    startMaps()
  }
})()

document.querySelectorAll(".language-switcher").forEach((form) => {
  form.addEventListener("submit", () => {
    const next = form.querySelector('[name="next"]')
    if (next) next.value = `${window.location.pathname}${window.location.search}${window.location.hash}`
  })
})


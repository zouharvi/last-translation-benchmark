import L, { Marker } from 'leaflet';

import 'leaflet/dist/leaflet.css';
import './assets/affiliation-map.css';

import { AffiliationMapAffiliation, AffiliationMapPlace } from './api';
import { esc as escapeHtml } from './utils';

const number = new Intl.NumberFormat('en');
const europeCenter: L.LatLngExpression = [52, 14];
const europeZoom = 4;

interface MarkerOffset {
    x: number;
    y: number;
}

function requiredElement<T extends HTMLElement>(selector: string): T {
    const element = document.querySelector<T>(selector);
    if (!element) throw new Error(`Missing map element: ${selector}`);
    return element;
}

function animateCounter(element: HTMLElement, value: number, duration = 1200): void {
    const target = Math.max(0, Math.round(value));
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
        element.textContent = number.format(target);
        return;
    }

    const startedAt = performance.now();
    element.textContent = '0';

    function update(now: number): void {
        const progress = Math.min((now - startedAt) / duration, 1);
        const easedProgress = 1 - (1 - progress) ** 3;
        element.textContent = number.format(Math.round(target * easedProgress));
        if (progress < 1) requestAnimationFrame(update);
    }

    requestAnimationFrame(update);
}

function placeKey(place: AffiliationMapPlace): string {
    return `${place.lat},${place.lng}`;
}

function affiliationKey(
    place: AffiliationMapPlace,
    affiliation: AffiliationMapAffiliation,
): string {
    return `${placeKey(place)}::${affiliation.name}`;
}

function affiliationInitials(name: string): string {
    const words = name
        .replace(/[^\p{L}\p{N}]+/gu, ' ')
        .trim()
        .split(/\s+/)
        .filter(Boolean);
    const meaningful = words.filter(
        (word) => !['of', 'for', 'the', 'and', 'für'].includes(word.toLocaleLowerCase()),
    );
    return (meaningful.length ? meaningful : words)
        .slice(0, 3)
        .map((word) => word[0])
        .join('')
        .toLocaleUpperCase();
}

function affiliationLogoUrl(domain: string): string {
    const website = `https://${domain}`;
    return `https://www.google.com/s2/favicons?domain_url=${encodeURIComponent(website)}&sz=128`;
}

function acceptedLabel(accepted: number): string {
    return `${number.format(accepted)} accepted ${accepted === 1 ? 'submission' : 'submissions'}`;
}

export function initializeAffiliationMap(
    places: AffiliationMapPlace[],
    totalSubmissions: number,
    totalAuthors: number,
): void {
    const detail = requiredElement<HTMLElement>('#affiliation-map-detail');
    const loading = requiredElement<HTMLElement>('#affiliation-map-loading');
    const toolbox = requiredElement<HTMLElement>('.affiliation-map-toolbox');
    const affiliationInput = requiredElement<HTMLInputElement>('#map-affiliation-filter');
    const affiliationOptions = requiredElement<HTMLDataListElement>('#map-affiliation-options');
    const countrySelect = requiredElement<HTMLSelectElement>('#map-country-filter');
    const filterStatus = requiredElement<HTMLElement>('#map-filter-status');
    const resetButton = requiredElement<HTMLButtonElement>('#map-reset');
    const totalSubmissionsElement = requiredElement<HTMLElement>('#map-total-submissions');
    const contributorCountElement = requiredElement<HTMLElement>('#map-contributor-count');

    const map = L.map('affiliation-map', {
        zoomControl: false,
        minZoom: 2,
        maxZoom: 18,
        worldCopyJump: true,
        maxBoundsViscosity: 0.8,
    }).setMaxBounds([[-85, -190], [85, 190]]);

    L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/attributions">CARTO</a>',
        subdomains: 'abcd',
        maxZoom: 20,
    }).addTo(map);
    L.control.zoom({ position: 'bottomleft' }).addTo(map);
    L.DomEvent.disableClickPropagation(toolbox);
    L.DomEvent.disableScrollPropagation(toolbox);

    const markerLayer = L.layerGroup().addTo(map);
    let selectedKey: string | null = null;
    const maximumAccepted = Math.max(
        ...places.flatMap((place) => place.affiliations.map((affiliation) => affiliation.accepted)),
        1,
    );
    const topAffiliationNames = new Set(
        places
            .flatMap((place) => place.affiliations)
            .filter((affiliation) => affiliation.name !== 'Other affiliations')
            .sort((left, right) => right.accepted - left.accepted || left.name.localeCompare(right.name))
            .slice(0, 5)
            .map((affiliation) => affiliation.name),
    );

    function searchableAffiliations(place: AffiliationMapPlace): AffiliationMapAffiliation[] {
        const query = affiliationInput.value.trim().toLocaleLowerCase();
        if (!query) return place.affiliations;
        return place.affiliations.filter((affiliation) =>
            [affiliation.name, ...affiliation.search_terms].some((term) =>
                term.toLocaleLowerCase().includes(query),
            ),
        );
    }

    function filteredPlaces(): AffiliationMapPlace[] {
        const country = countrySelect.value;
        return places.filter(
            (place) => (!country || place.country === country) && searchableAffiliations(place).length,
        );
    }

    function markerSize(accepted: number): number {
        const ratio = Math.sqrt(accepted / maximumAccepted);
        return Math.round(32 + ratio * 16);
    }

    function affiliationOffsets(affiliations: AffiliationMapAffiliation[]): MarkerOffset[] {
        if (affiliations.length === 1) return [{ x: 0, y: 0 }];
        const largestSize = Math.max(...affiliations.map((affiliation) => markerSize(affiliation.accepted)));
        const step = Math.ceil(largestSize * 1.05);
        const y = -Math.ceil(largestSize * 0.72);
        return affiliations.map((_, index) => ({
            x: Math.round((index - (affiliations.length - 1) / 2) * step),
            y,
        }));
    }

    function markerIcon(
        place: AffiliationMapPlace,
        affiliation: AffiliationMapAffiliation,
        offset: MarkerOffset,
    ): L.DivIcon {
        const size = markerSize(affiliation.accepted);
        const selectedClass = affiliationKey(place, affiliation) === selectedKey ? ' is-selected' : '';
        const isTopFive = topAffiliationNames.has(affiliation.name);
        const image = affiliation.logo_domain
            ? `<img class="affiliation-logo-image" src="${escapeHtml(affiliationLogoUrl(affiliation.logo_domain))}" alt="" decoding="async" referrerpolicy="no-referrer" onerror="this.hidden=true;this.nextElementSibling.hidden=false">`
            : '';
        const hiddenFallback = affiliation.logo_domain ? ' hidden' : '';
        const fire = isTopFive ? '<span class="top-five-fire" aria-hidden="true">🔥</span>' : '';
        const accessibleLabel = `${affiliation.name}, ${acceptedLabel(affiliation.accepted)}${isTopFive ? ', top-five affiliation' : ''}`;

        return L.divIcon({
            className: 'affiliation-marker-wrap',
            html: `
                <span class="affiliation-logo-marker${selectedClass}" style="--logo-size:${size}px" role="img" aria-label="${escapeHtml(accessibleLabel)}">
                    <span class="affiliation-logo${isTopFive ? ' is-top-five' : ''}">
                        ${image}
                        <span class="affiliation-logo-fallback"${hiddenFallback}>${escapeHtml(affiliationInitials(affiliation.name))}</span>
                        ${fire}
                    </span>
                </span>
            `,
            iconSize: [size, size],
            iconAnchor: [size / 2 - offset.x, size / 2 - offset.y],
            tooltipAnchor: [offset.x, offset.y - (size / 2 + 8)],
        });
    }

    function tooltipContent(
        place: AffiliationMapPlace,
        affiliation: AffiliationMapAffiliation,
    ): string {
        const precisionNote = place.precision !== 'exact'
            ? '<small>Approximate location</small>'
            : '';
        const topFiveNote = topAffiliationNames.has(affiliation.name)
            ? '<small class="top-five-note">🔥 Top 5 affiliation</small>'
            : '';
        return `
            <strong>${escapeHtml(affiliation.name)}</strong>
            <span>${escapeHtml(place.city)}, ${escapeHtml(place.country)}</span>
            <small>${acceptedLabel(affiliation.accepted)}</small>
            ${precisionNote}
            ${topFiveNote}
        `;
    }

    function renderDetail(
        place: AffiliationMapPlace | null,
        affiliation: AffiliationMapAffiliation | null,
    ): void {
        if (!place || !affiliation) {
            detail.textContent = 'Select an institution logo to inspect its contributors.';
            return;
        }
        const authors = affiliation.authors
            .map((author) => `${escapeHtml(author.name)} (${number.format(author.accepted)})`)
            .join(' · ');
        const precisionNote = place.precision !== 'exact'
            ? '<div class="affiliation-detail-location">Approximate location</div>'
            : '';
        detail.innerHTML = `
            <div class="affiliation-detail-heading">
                <strong>${escapeHtml(affiliation.name)}</strong>
                <span>${acceptedLabel(affiliation.accepted)}</span>
            </div>
            <div class="affiliation-detail-location">${escapeHtml(place.city)}, ${escapeHtml(place.country)}</div>
            ${precisionNote}
            <div class="affiliation-author-list">${authors}</div>
        `;
    }

    function setSelectedMarker(marker: Marker | null): void {
        document.querySelectorAll('.affiliation-logo-marker.is-selected').forEach((logo) => {
            logo.classList.remove('is-selected');
        });
        marker?.getElement()?.querySelector('.affiliation-logo-marker')?.classList.add('is-selected');
    }

    function renderMarkers(): AffiliationMapPlace[] {
        const visible = filteredPlaces();
        const visibleKeys = new Set(
            visible.flatMap((place) =>
                searchableAffiliations(place).map((affiliation) => affiliationKey(place, affiliation)),
            ),
        );
        if (selectedKey && !visibleKeys.has(selectedKey)) {
            selectedKey = null;
            renderDetail(null, null);
        }

        markerLayer.clearLayers();
        visible.forEach((place) => {
            const affiliations = searchableAffiliations(place);
            const offsets = affiliationOffsets(affiliations);
            affiliations.forEach((affiliation, index) => {
                const isTopFive = topAffiliationNames.has(affiliation.name);
                const marker = L.marker([place.lat, place.lng], {
                    icon: markerIcon(place, affiliation, offsets[index]),
                    keyboard: true,
                    alt: `${affiliation.name}, ${place.city}, ${place.country}, ${acceptedLabel(affiliation.accepted)}${isTopFive ? ', top-five affiliation' : ''}`,
                    riseOnHover: true,
                    zIndexOffset: affiliations.length > 1 ? 1000 + affiliations.length - index : 0,
                });
                marker.bindTooltip(tooltipContent(place, affiliation), {
                    className: 'affiliation-location-tooltip',
                    direction: 'top',
                    opacity: 1,
                });
                marker.on('click', () => {
                    selectedKey = affiliationKey(place, affiliation);
                    setSelectedMarker(marker);
                    renderDetail(place, affiliation);
                });
                marker.addTo(markerLayer);
            });
        });

        const accepted = visible.reduce(
            (total, place) => total + searchableAffiliations(place).reduce(
                (placeTotal, affiliation) => placeTotal + affiliation.accepted,
                0,
            ),
            0,
        );
        const affiliationCount = visible.reduce(
            (total, place) => total + searchableAffiliations(place).length,
            0,
        );
        filterStatus.textContent = `${number.format(affiliationCount)} ${affiliationCount === 1 ? 'affiliation' : 'affiliations'} · ${number.format(accepted)} accepted submissions`;
        return visible;
    }

    function fitPlaces(visible: AffiliationMapPlace[], maximumZoom = 7): void {
        if (!visible.length) return;
        if (visible.length === 1) {
            map.flyTo([visible[0].lat, visible[0].lng], 8, { duration: 0.65 });
            return;
        }
        const compact = map.getSize().x <= 720;
        const bounds = L.latLngBounds(visible.map((place) => [place.lat, place.lng]));
        map.flyToBounds(bounds, {
            paddingTopLeft: [24, 24],
            paddingBottomRight: compact ? [24, 240] : [310, 220],
            maxZoom: maximumZoom,
            duration: 0.65,
        });
    }

    function resetView(): void {
        affiliationInput.value = '';
        countrySelect.value = '';
        selectedKey = null;
        renderDetail(null, null);
        renderMarkers();
        map.flyTo(europeCenter, europeZoom, { duration: 0.65 });
    }

    const affiliationNames = Array.from(
        new Set(places.flatMap((place) => place.affiliations.map((affiliation) => affiliation.name))),
    ).sort((left, right) => left.localeCompare(right));
    affiliationOptions.replaceChildren(
        ...affiliationNames.map((affiliation) => {
            const option = document.createElement('option');
            option.value = affiliation;
            return option;
        }),
    );
    const countries = Array.from(new Set(places.map((place) => place.country))).sort(
        (left, right) => left.localeCompare(right),
    );
    countrySelect.append(
        ...countries.map((country) => {
            const option = document.createElement('option');
            option.value = country;
            option.textContent = country;
            return option;
        }),
    );

    affiliationInput.addEventListener('input', renderMarkers);
    affiliationInput.addEventListener('change', () => fitPlaces(filteredPlaces(), 9));
    countrySelect.addEventListener('change', () => {
        const visible = renderMarkers();
        if (countrySelect.value) fitPlaces(visible, 7);
    });
    resetButton.addEventListener('click', resetView);
    map.on('click', () => {
        selectedKey = null;
        setSelectedMarker(null);
        renderDetail(null, null);
    });

    animateCounter(totalSubmissionsElement, totalSubmissions);
    animateCounter(contributorCountElement, totalAuthors);
    renderMarkers();
    map.setView(europeCenter, europeZoom);
    loading.hidden = true;
}

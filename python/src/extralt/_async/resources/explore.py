from __future__ import annotations

import datetime as dt

from ..._operation import operation
from ...types import (
    ActivityEventList,
    ActivityInterval,
    ActivityKind,
    AssortmentOverlapAnalysis,
    AssortmentOverlapRow,
    AvailabilityChangeRow,
    AvailabilityChangesAnalysis,
    Change,
    ChangeEntity,
    ChangeEvent,
    ChangePage,
    ChangeWindow,
    CountryCode,
    CurrencyCode,
    EntityKind,
    EntityLookup,
    ExploreActivity,
    ExploreFacets,
    ExploreOverview,
    ExploreStores,
    HistoryInterval,
    MarketVariant,
    MarketVariantPage,
    MarketVariantSort,
    ObservedSort,
    Offer,
    OfferCondition,
    OfferPage,
    PriceMovementRow,
    PriceMovementsAnalysis,
    PriceMovementSort,
    PricePositionAnalysis,
    PricePositionRow,
    RelationshipGraph,
    Variant,
    VariantHistoryPage,
    VariantHistoryPoint,
    VariantPriceSeries,
)
from .._http import AsyncHTTP
from .._pagination import AsyncPaginator
from .._resource import AsyncResource

Timestamp = dt.datetime | str
"""An aware `datetime` or an RFC 3339 string such as `2026-01-31T00:00:00Z`."""


class AsyncExplore:
    """Observed market evidence over Stores, Products, Variants, Listings and Offers."""

    def __init__(self, http: AsyncHTTP) -> None:
        self.overview = AsyncOverview(http)
        self.facets = AsyncFacets(http)
        self.activity = AsyncActivity(http)
        self.stores = AsyncStores(http)
        self.entities = AsyncEntities(http)
        self.relationships = AsyncRelationships(http)
        self.changes = AsyncChanges(http)
        self.markets = AsyncMarkets(http)
        self.variants = AsyncVariants(http)
        self.analyses = AsyncAnalyses(http)


class AsyncOverview(AsyncResource):
    @operation("get_overview")
    async def get(self, *, timeout: float | None = None) -> ExploreOverview:
        """Totals and coverage by country, category and Store."""
        return await self._call("get_overview", ExploreOverview, timeout=timeout)


class AsyncFacets(AsyncResource):
    @operation("get_facets")
    async def get(
        self,
        *,
        country: CountryCode | None = None,
        currency: CurrencyCode | None = None,
        condition: OfferCondition | None = None,
        category_id: str | None = None,
        brand: str | None = None,
        store_id: str | None = None,
        limit: int | None = None,
        timeout: float | None = None,
    ) -> ExploreFacets:
        """Filter values available within a scope, `limit` per dimension."""
        return await self._call(
            "get_facets",
            ExploreFacets,
            params={
                "country": country,
                "currency": currency,
                "condition": condition,
                "category_id": category_id,
                "brand": brand,
                "store_id": store_id,
                "limit": limit,
            },
            timeout=timeout,
        )


class AsyncActivity(AsyncResource):
    @operation("get_activity")
    async def get(
        self,
        *,
        from_: Timestamp,
        bucket: ActivityInterval,
        to: Timestamp | None = None,
        timeout: float | None = None,
    ) -> ExploreActivity:
        """Counts of price, availability and Listing events between `from_` and `to` (now)."""
        return await self._call(
            "get_activity",
            ExploreActivity,
            params={"from": from_, "to": to, "bucket": bucket},
            timeout=timeout,
        )

    @operation("list_activity_events")
    async def events(
        self,
        *,
        from_: Timestamp,
        kind: ActivityKind,
        to: Timestamp | None = None,
        store_id: str | None = None,
        limit: int | None = None,
        timeout: float | None = None,
    ) -> ActivityEventList:
        """The largest or latest events of one kind in the window, at most `limit`."""
        return await self._call(
            "list_activity_events",
            ActivityEventList,
            params={"from": from_, "to": to, "kind": kind, "store_id": store_id, "limit": limit},
            timeout=timeout,
        )


class AsyncStores(AsyncResource):
    @operation("list_stores")
    async def list(
        self, *, max_staleness_days: int | None = None, timeout: float | None = None
    ) -> ExploreStores:
        """Every observed Store with its current state, and per-country totals."""
        return await self._call(
            "list_stores",
            ExploreStores,
            params={"max_staleness_days": max_staleness_days},
            timeout=timeout,
        )


class AsyncEntities(AsyncResource):
    @operation("lookup_entities")
    async def lookup(
        self,
        *,
        kind: EntityKind,
        search: str | None = None,
        id: str | None = None,
        variant_id: str | None = None,
        timeout: float | None = None,
    ) -> EntityLookup:
        """Finds Store, Product, Variant or Listing ids by text, or resolves one `id`."""
        return await self._call(
            "lookup_entities",
            EntityLookup,
            params={"kind": kind, "search": search, "id": id, "variant_id": variant_id},
            timeout=timeout,
        )


class AsyncRelationships(AsyncResource):
    @operation("get_relationships")
    async def get(
        self,
        *,
        from_: Timestamp | None = None,
        to: Timestamp | None = None,
        timeout: float | None = None,
    ) -> RelationshipGraph:
        """Product, Variant, Listing and Offer counts, for all evidence or one time range."""
        return await self._call(
            "get_relationships",
            RelationshipGraph,
            params={"from": from_, "to": to},
            timeout=timeout,
        )


class AsyncChanges(AsyncResource):
    @operation("list_changes")
    def list(
        self,
        *,
        window: ChangeWindow,
        to: Timestamp | None = None,
        entity: ChangeEntity | None = None,
        event: ChangeEvent | None = None,
        product_id: str | None = None,
        variant_id: str | None = None,
        listing_id: str | None = None,
        store_id: str | None = None,
        country: CountryCode | None = None,
        currency: CurrencyCode | None = None,
        condition: OfferCondition | None = None,
        sort: ObservedSort | None = None,
        summary_only: bool | None = None,
        limit: int | None = None,
        cursor: str | None = None,
    ) -> AsyncPaginator[ChangePage, Change]:
        """Changes observed in the `window` ending at `to` (now).

        Every page carries the full-scope `count` and `summary`. Pass the first page's `to` to
        later calls to keep the window fixed.
        """
        return AsyncPaginator(
            self._http,
            "list_changes",
            ChangePage,
            items="data",
            params={
                "window": window,
                "to": to,
                "entity": entity,
                "event": event,
                "product_id": product_id,
                "variant_id": variant_id,
                "listing_id": listing_id,
                "store_id": store_id,
                "country": country,
                "currency": currency,
                "condition": condition,
                "sort": sort,
                "summary_only": summary_only,
                "limit": limit,
                "cursor": cursor,
            },
        )


class AsyncMarkets(AsyncResource):
    @operation("list_market_variants")
    def list(
        self,
        *,
        country: CountryCode | None = None,
        condition: OfferCondition | None = None,
        category_id: str | None = None,
        brand: str | None = None,
        store_id: str | None = None,
        variant_id: str | None = None,
        sort: MarketVariantSort | None = None,
        limit: int | None = None,
        cursor: str | None = None,
    ) -> AsyncPaginator[MarketVariantPage, MarketVariant]:
        """Current Variants with their prices, availability and Store coverage."""
        return AsyncPaginator(
            self._http,
            "list_market_variants",
            MarketVariantPage,
            items="data",
            params={
                "country": country,
                "condition": condition,
                "category_id": category_id,
                "brand": brand,
                "store_id": store_id,
                "variant_id": variant_id,
                "sort": sort,
                "limit": limit,
                "cursor": cursor,
            },
        )


class AsyncVariants(AsyncResource):
    @operation("get_variant")
    async def get(self, variant_id: str, *, timeout: float | None = None) -> Variant:
        """One Variant with its identity, lifecycle, field evidence and review signals."""
        return await self._call(
            "get_variant", Variant, path_params={"variant_id": variant_id}, timeout=timeout
        )

    @operation("list_variant_offers")
    def offers(
        self, variant_id: str, *, limit: int | None = None, cursor: str | None = None
    ) -> AsyncPaginator[OfferPage, Offer]:
        """The Variant's current Offers across Stores and sellers."""
        return AsyncPaginator(
            self._http,
            "list_variant_offers",
            OfferPage,
            items="data",
            path_params={"variant_id": variant_id},
            params={"limit": limit, "cursor": cursor},
        )

    @operation("list_variant_history")
    def history(
        self,
        variant_id: str,
        *,
        from_: Timestamp,
        to: Timestamp,
        country: CountryCode,
        currency: CurrencyCode,
        condition: OfferCondition,
        listing_id: str | None = None,
        interval: HistoryInterval | None = None,
        sort: ObservedSort | None = None,
        limit: int | None = None,
        cursor: str | None = None,
    ) -> AsyncPaginator[VariantHistoryPage, VariantHistoryPoint]:
        """Lowest-price evidence for one market of the Variant, at most 366 days."""
        return AsyncPaginator(
            self._http,
            "list_variant_history",
            VariantHistoryPage,
            items="data",
            path_params={"variant_id": variant_id},
            params={
                "from": from_,
                "to": to,
                "country": country,
                "currency": currency,
                "condition": condition,
                "listing_id": listing_id,
                "interval": interval,
                "sort": sort,
                "limit": limit,
                "cursor": cursor,
            },
        )

    @operation("get_variant_price_series")
    async def price_series(
        self,
        variant_id: str,
        *,
        from_: Timestamp,
        to: Timestamp,
        country: CountryCode,
        currency: CurrencyCode,
        condition: OfferCondition,
        listing_id: str | None = None,
        interval: HistoryInterval | None = None,
        timeout: float | None = None,
    ) -> VariantPriceSeries:
        """The complete lowest-price series for one market of the Variant, never truncated."""
        return await self._call(
            "get_variant_price_series",
            VariantPriceSeries,
            path_params={"variant_id": variant_id},
            params={
                "from": from_,
                "to": to,
                "country": country,
                "currency": currency,
                "condition": condition,
                "listing_id": listing_id,
                "interval": interval,
            },
            timeout=timeout,
        )


class AsyncAnalyses(AsyncResource):
    """Packaged Analyses. `first_page()` returns the Analysis, whose summary, coverage and
    freshness describe the whole scope; iterating yields every evidence row across pages."""

    @operation("analyze_price_position")
    def price_position(
        self,
        *,
        reference_store_id: str,
        country: CountryCode,
        currency: CurrencyCode,
        condition: OfferCondition | None = None,
        category_id: str | None = None,
        brand: str | None = None,
        max_staleness_days: int | None = None,
        limit: int | None = None,
        cursor: str | None = None,
    ) -> AsyncPaginator[PricePositionAnalysis, PricePositionRow]:
        """Each current Variant's price at the reference Store against its competitors."""
        return AsyncPaginator(
            self._http,
            "analyze_price_position",
            PricePositionAnalysis,
            items="data",
            params={
                "reference_store_id": reference_store_id,
                "country": country,
                "currency": currency,
                "condition": condition,
                "category_id": category_id,
                "brand": brand,
                "max_staleness_days": max_staleness_days,
                "limit": limit,
                "cursor": cursor,
            },
        )

    @operation("analyze_price_movements")
    def price_movements(
        self,
        *,
        from_: Timestamp,
        country: CountryCode,
        currency: CurrencyCode,
        condition: OfferCondition | None = None,
        store_id: str | None = None,
        category_id: str | None = None,
        brand: str | None = None,
        sort: PriceMovementSort | None = None,
        limit: int | None = None,
        cursor: str | None = None,
    ) -> AsyncPaginator[PriceMovementsAnalysis, PriceMovementRow]:
        """Net price change of each Listing/seller series since `from_`, at most 90 days ago."""
        return AsyncPaginator(
            self._http,
            "analyze_price_movements",
            PriceMovementsAnalysis,
            items="data",
            params={
                "from": from_,
                "country": country,
                "currency": currency,
                "condition": condition,
                "store_id": store_id,
                "category_id": category_id,
                "brand": brand,
                "sort": sort,
                "limit": limit,
                "cursor": cursor,
            },
        )

    @operation("analyze_availability_changes")
    def availability_changes(
        self,
        *,
        from_: Timestamp,
        country: CountryCode,
        condition: OfferCondition | None = None,
        store_id: str | None = None,
        category_id: str | None = None,
        brand: str | None = None,
        limit: int | None = None,
        cursor: str | None = None,
    ) -> AsyncPaginator[AvailabilityChangesAnalysis, AvailabilityChangeRow]:
        """Current availability of each Offer series and its net change since `from_`."""
        return AsyncPaginator(
            self._http,
            "analyze_availability_changes",
            AvailabilityChangesAnalysis,
            items="data",
            params={
                "from": from_,
                "country": country,
                "condition": condition,
                "store_id": store_id,
                "category_id": category_id,
                "brand": brand,
                "limit": limit,
                "cursor": cursor,
            },
        )

    @operation("analyze_assortment_overlap")
    def assortment_overlap(
        self,
        *,
        reference_store_id: str,
        comparison_store_id: str,
        country: CountryCode,
        category_id: str | None = None,
        brand: str | None = None,
        max_staleness_days: int | None = None,
        limit: int | None = None,
        cursor: str | None = None,
    ) -> AsyncPaginator[AssortmentOverlapAnalysis, AssortmentOverlapRow]:
        """Variants the two Stores share or carry alone, excluding stale Listings."""
        return AsyncPaginator(
            self._http,
            "analyze_assortment_overlap",
            AssortmentOverlapAnalysis,
            items="data",
            params={
                "reference_store_id": reference_store_id,
                "comparison_store_id": comparison_store_id,
                "country": country,
                "category_id": category_id,
                "brand": brand,
                "max_staleness_days": max_staleness_days,
                "limit": limit,
                "cursor": cursor,
            },
        )

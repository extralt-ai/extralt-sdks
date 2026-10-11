import type { HTTP } from '../core/http.js';
import { Paginator } from '../core/pagination.js';
import { Resource } from '../core/resource.js';
import type { CallOptions, QueryParams } from '../core/types.js';
import type {
  ActivityEventList,
  AssortmentOverlapRow,
  AvailabilityChangeRow,
  Change,
  EntityLookup,
  ExploreActivity,
  ExploreFacets,
  ExploreOverview,
  ExploreStores,
  MarketVariant,
  Offer,
  PriceMovementRow,
  PricePositionRow,
  RelationshipGraph,
  Variant,
  VariantHistoryPoint,
  VariantPriceSeries,
} from '../generated/openapi.js';

/**
 * Observed market evidence over Stores, Products, Variants, Listings and Offers. Time parameters
 * are RFC 3339 strings, such as `new Date().toISOString()`.
 */
export class Explore {
  readonly overview: Overview;
  readonly facets: Facets;
  readonly activity: Activity;
  readonly stores: Stores;
  readonly entities: Entities;
  readonly relationships: Relationships;
  readonly changes: Changes;
  readonly markets: Markets;
  readonly variants: Variants;
  readonly analyses: Analyses;

  constructor(http: HTTP) {
    this.overview = new Overview(http);
    this.facets = new Facets(http);
    this.activity = new Activity(http);
    this.stores = new Stores(http);
    this.entities = new Entities(http);
    this.relationships = new Relationships(http);
    this.changes = new Changes(http);
    this.markets = new Markets(http);
    this.variants = new Variants(http);
    this.analyses = new Analyses(http);
  }
}

export class Overview extends Resource {
  /** Totals and coverage by country, category and Store. */
  get(options: CallOptions = {}): Promise<ExploreOverview> {
    return this.http.request('get_overview', options);
  }
}

export class Facets extends Resource {
  /** Filter values available within a scope, `limit` per dimension. */
  get(query: QueryParams<'get_facets'> = {}, options: CallOptions = {}): Promise<ExploreFacets> {
    return this.http.request('get_facets', { query, ...options });
  }
}

export class Activity extends Resource {
  /** Counts of price, availability and Listing events between `from` and `to` (now). */
  get(query: QueryParams<'get_activity'>, options: CallOptions = {}): Promise<ExploreActivity> {
    return this.http.request('get_activity', { query, ...options });
  }

  /** The largest or latest events of one kind in the window, at most `limit`. */
  events(
    query: QueryParams<'list_activity_events'>,
    options: CallOptions = {},
  ): Promise<ActivityEventList> {
    return this.http.request('list_activity_events', { query, ...options });
  }
}

export class Stores extends Resource {
  /** Every observed Store with its current state, and per-country totals. */
  list(query: QueryParams<'list_stores'> = {}, options: CallOptions = {}): Promise<ExploreStores> {
    return this.http.request('list_stores', { query, ...options });
  }
}

export class Entities extends Resource {
  /** Finds Store, Product, Variant or Listing ids by text, or resolves one `id`. */
  lookup(query: QueryParams<'lookup_entities'>, options: CallOptions = {}): Promise<EntityLookup> {
    return this.http.request('lookup_entities', { query, ...options });
  }
}

export class Relationships extends Resource {
  /** Product, Variant, Listing and Offer counts, for all evidence or one time range. */
  get(
    query: QueryParams<'get_relationships'> = {},
    options: CallOptions = {},
  ): Promise<RelationshipGraph> {
    return this.http.request('get_relationships', { query, ...options });
  }
}

export class Changes extends Resource {
  /**
   * Changes observed in the `window` ending at `to` (now). Every page carries the full-scope
   * `count` and `summary`; pass the first page's `to` to later calls to keep the window fixed.
   */
  list(
    query: QueryParams<'list_changes'>,
    options: CallOptions = {},
  ): Paginator<'list_changes', Change> {
    return new Paginator(this.http, 'list_changes', { query, ...options }, (page) => page.data);
  }
}

export class Markets extends Resource {
  /** Current Variants with their prices, availability and Store coverage. */
  list(
    query: QueryParams<'list_market_variants'> = {},
    options: CallOptions = {},
  ): Paginator<'list_market_variants', MarketVariant> {
    return new Paginator(
      this.http,
      'list_market_variants',
      { query, ...options },
      (page) => page.data,
    );
  }
}

export class Variants extends Resource {
  /** One Variant with its identity, lifecycle, field evidence and review signals. */
  get(variantId: string, options: CallOptions = {}): Promise<Variant> {
    return this.http.request('get_variant', { path: { variant_id: variantId }, ...options });
  }

  /** The Variant's current Offers across Stores and sellers. */
  offers(
    variantId: string,
    query: QueryParams<'list_variant_offers'> = {},
    options: CallOptions = {},
  ): Paginator<'list_variant_offers', Offer> {
    return new Paginator(
      this.http,
      'list_variant_offers',
      { path: { variant_id: variantId }, query, ...options },
      (page) => page.data,
    );
  }

  /** Lowest-price evidence for one market of the Variant, at most 366 days. */
  history(
    variantId: string,
    query: QueryParams<'list_variant_history'>,
    options: CallOptions = {},
  ): Paginator<'list_variant_history', VariantHistoryPoint> {
    return new Paginator(
      this.http,
      'list_variant_history',
      { path: { variant_id: variantId }, query, ...options },
      (page) => page.data,
    );
  }

  /** The complete lowest-price series for one market of the Variant, never truncated. */
  priceSeries(
    variantId: string,
    query: QueryParams<'get_variant_price_series'>,
    options: CallOptions = {},
  ): Promise<VariantPriceSeries> {
    return this.http.request('get_variant_price_series', {
      path: { variant_id: variantId },
      query,
      ...options,
    });
  }
}

/**
 * Packaged Analyses. `firstPage()` returns the Analysis, whose summary, coverage and freshness
 * describe the whole scope; iterating yields every evidence row across pages.
 */
export class Analyses extends Resource {
  /** Each current Variant's price at the reference Store against its competitors. */
  pricePosition(
    query: QueryParams<'analyze_price_position'>,
    options: CallOptions = {},
  ): Paginator<'analyze_price_position', PricePositionRow> {
    return new Paginator(
      this.http,
      'analyze_price_position',
      { query, ...options },
      (page) => page.data,
    );
  }

  /** Net price change of each Listing/seller series since `from`, at most 90 days ago. */
  priceMovements(
    query: QueryParams<'analyze_price_movements'>,
    options: CallOptions = {},
  ): Paginator<'analyze_price_movements', PriceMovementRow> {
    return new Paginator(
      this.http,
      'analyze_price_movements',
      { query, ...options },
      (page) => page.data,
    );
  }

  /** Current availability of each Offer series and its net change since `from`. */
  availabilityChanges(
    query: QueryParams<'analyze_availability_changes'>,
    options: CallOptions = {},
  ): Paginator<'analyze_availability_changes', AvailabilityChangeRow> {
    return new Paginator(
      this.http,
      'analyze_availability_changes',
      { query, ...options },
      (page) => page.data,
    );
  }

  /** Variants the two Stores share or carry alone, excluding stale Listings. */
  assortmentOverlap(
    query: QueryParams<'analyze_assortment_overlap'>,
    options: CallOptions = {},
  ): Paginator<'analyze_assortment_overlap', AssortmentOverlapRow> {
    return new Paginator(
      this.http,
      'analyze_assortment_overlap',
      { query, ...options },
      (page) => page.data,
    );
  }
}

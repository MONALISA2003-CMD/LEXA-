"use client";

import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { AppShell } from "../../components/app-shell";
import { Badge, ResponsiveDataTable } from "../../components/ui";
import {
  createBarcode, createPrice, createPriceList, createProduct, createVariant,
  getBarcodes, getBrands, getBusinessProfile, getCatalogLookup, getCategories, getInventoryBalances, getPriceLists,
  getPrices, getProduct, getProducts, getUnits, getVariants, updateVariant,
  type Barcode, type Brand, type Category, type InventoryBalance,
  type PriceList, type Product, type ProductPrice, type Unit, type Variant,
} from "../../lib/api";

type DetailTab = "Overview" | "Variants" | "Pricing" | "Barcodes" | "Inventory";
function money(value: string | number, currency: string | null | undefined) {
  if (!currency || !/^[A-Z]{3}$/.test(currency)) return "Business currency not set";
  try { return new Intl.NumberFormat("en-UG", { style: "currency", currency, maximumFractionDigits: 0 }).format(Number(value)); }
  catch { return `${currency} ${Number(value).toLocaleString("en-UG", { maximumFractionDigits: 0 })}`; }
}
function dateTimeInput() { const local = new Date(Date.now() - new Date().getTimezoneOffset() * 60000); return local.toISOString().slice(0, 16); }
function iso(value: string) { return new Date(value).toISOString(); }
function short(id: string) { return `${id.slice(0, 8)}…`; }

export default function ProductsPage() {
  const [products, setProducts] = useState<Product[]>([]), [categories, setCategories] = useState<Category[]>([]), [brands, setBrands] = useState<Brand[]>([]), [units, setUnits] = useState<Unit[]>([]), [priceLists, setPriceLists] = useState<PriceList[]>([]);
  const [variants, setVariants] = useState<Variant[]>([]), [selected, setSelected] = useState<Product | null>(null), [selectedVariant, setSelectedVariant] = useState<Variant | null>(null), [prices, setPrices] = useState<ProductPrice[]>([]), [barcodes, setBarcodes] = useState<Barcode[]>([]), [balances, setBalances] = useState<InventoryBalance[]>([]);
  const [tab, setTab] = useState<DetailTab>("Overview"), [search, setSearch] = useState(""), [busy, setBusy] = useState(false), [message, setMessage] = useState("");
  const [businessCurrency, setBusinessCurrency] = useState<string | null>(null);
  const [referencesState, setReferencesState] = useState<"loading" | "success" | "error">("loading");
  const productRequestId = useRef(0);
  const [catalogState, setCatalogState] = useState<"loading" | "success" | "error">("loading");
  const [productName, setProductName] = useState(""), [productDescription, setProductDescription] = useState(""), [category, setCategory] = useState(""), [brand, setBrand] = useState("");
  const [variantName, setVariantName] = useState(""), [sku, setSku] = useState(""), [unit, setUnit] = useState(""), [variantCosting, setVariantCosting] = useState("WEIGHTED_AVERAGE");
  const [barcode, setBarcode] = useState(""), [barcodeType, setBarcodeType] = useState("EAN"), [barcodePrimary, setBarcodePrimary] = useState(false);
  const [priceListName, setPriceListName] = useState(""), [priceListType, setPriceListType] = useState("RETAIL"), [effectiveFrom, setEffectiveFrom] = useState(dateTimeInput()), [priceListCurrency, setPriceListCurrency] = useState(""), [priceListId, setPriceListId] = useState(""), [priceValue, setPriceValue] = useState(""), [minimumQuantity, setMinimumQuantity] = useState("1");

  const categoryMap = useMemo(() => new Map(categories.map((x) => [x.id, x.name])), [categories]);
  const brandMap = useMemo(() => new Map(brands.map((x) => [x.id, x.name])), [brands]);
  const unitMap = useMemo(() => new Map(units.map((x) => [x.id, x])), [units]);
  const priceListMap = useMemo(() => new Map(priceLists.map((x) => [x.id, x])), [priceLists]);

  async function loadCatalog(query = search, signal?: AbortSignal) {
    const requestId = ++productRequestId.current;
    setCatalogState("loading");
    try {
      const normalized = query.trim();
      const [result, matches] = await Promise.all([
        getProducts(normalized, signal),
        normalized ? getCatalogLookup(normalized, signal) : Promise.resolve([]),
      ]);
      const found = new Map(result.items.map((product) => [product.id, product]));
      const missingProductIds = [...new Set(matches.map((match) => match.product_id))]
        .filter((id) => !found.has(id)).slice(0, 10);
      const details = await Promise.allSettled(missingProductIds.map((id) => getProduct(id, signal)));
      if (signal?.aborted || requestId !== productRequestId.current) return;
      let detailFailures = 0;
      for (const detail of details) {
        if (detail.status === "fulfilled") found.set(detail.value.id, detail.value);
        else detailFailures += 1;
      }
      if (!result.items.length && missingProductIds.length > 0 && detailFailures === details.length) {
        throw new Error("A product code or barcode matched, but product details could not be loaded. Please try again.");
      }
      setProducts([...found.values()]);
      setCatalogState("success");
    } catch (error) {
      // Aborted or superseded searches are expected during quick typing and
      // must not replace a newer result with a stale error.
      if (signal?.aborted || requestId !== productRequestId.current) return;
      setCatalogState("error");
      setMessage(error instanceof Error ? error.message : "Unable to load the product products.");
    }
  }

  async function loadCatalogReferences() {
    setReferencesState("loading");
    try {
      const [c, b, u, pl] = await Promise.all([getCategories(), getBrands(), getUnits(), getPriceLists()]);
      setCategories(c.items); setBrands(b.items); setUnits(u.items); setPriceLists(pl);
      setCategory((current) => current || c.items[0]?.id || "");
      setUnit((current) => current || u.items[0]?.id || "");
      setPriceListId((current) => current || pl[0]?.id || "");
      setReferencesState("success");
    } catch (error) {
      setReferencesState("error");
      setMessage(error instanceof Error ? error.message : "Products reference data could not be loaded.");
    }
  }

  useEffect(() => {
    const controller = new AbortController();
    const timer = window.setTimeout(() => void loadCatalog(search, controller.signal), 250);
    return () => { window.clearTimeout(timer); controller.abort(); };
  }, [search]);
  useEffect(() => {
    let active = true;
    void getBusinessProfile().then((profile) => {
      if (!active) return;
      const code = profile?.currency_code && /^[A-Z]{3}$/i.test(profile.currency_code) ? profile.currency_code.toUpperCase() : null;
      setBusinessCurrency(code);
      setPriceListCurrency((current) => current || code || "");
    }).catch(() => { if (active) setBusinessCurrency(null); });
    return () => { active = false; };
  }, []);
  useEffect(() => { void loadCatalogReferences(); }, []);
  useEffect(() => {
    const query = new URLSearchParams(window.location.search).get("q");
    if (query) setSearch(query);
  }, []);

  async function loadVariantDetail(variant: Variant) {
    setSelectedVariant(variant);
    try {
      const [nextPrices, nextBarcodes, nextBalances] = await Promise.all([getPrices({ variant_id: variant.id }), getBarcodes(variant.id), getInventoryBalances({ variant_id: variant.id })]);
      setPrices(nextPrices); setBarcodes(nextBarcodes); setBalances(nextBalances);
    } catch (error) { setMessage(error instanceof Error ? error.message : "Unable to load pack-size or option details."); }
  }

  async function loadProductDetail(product: Product, preferredVariantId?: string) {
    setSelected(product); setTab("Overview"); setSelectedVariant(null); setPrices([]); setBarcodes([]); setBalances([]);
    try { const nextVariants = await getVariants(product.id); setVariants(nextVariants); const next = nextVariants.find((v) => v.id === preferredVariantId) || nextVariants[0] || null; if (next) await loadVariantDetail(next); }
    catch (error) { setMessage(error instanceof Error ? error.message : "Unable to load product details."); }
  }

  async function addProduct(event: FormEvent) {
    event.preventDefault(); if (!productName.trim() || !category) return; setBusy(true);
    try {
      const product = await createProduct({ name: productName.trim(), description: productDescription.trim() || null, category_id: category, brand_id: brand || null, has_variants: true });
      setProductName(""); setProductDescription(""); setMessage("Product created. Add a pack size or option and a product code before selling it."); await loadCatalog(); await loadProductDetail(product);
    } catch (error) { setMessage(error instanceof Error ? error.message : "Could not create the product."); } finally { setBusy(false); }
  }

  async function addVariant(event: FormEvent) {
    event.preventDefault(); if (!selected || !variantName.trim() || !sku.trim() || !unit) return; setBusy(true);
    try {
      const variant = await createVariant({ product_id: selected.id, name: variantName.trim(), sku: sku.trim().toUpperCase(), base_unit_id: unit, costing_method: variantCosting });
      setVariantName(""); setSku(""); setMessage("Pack size or option saved with its own product code and purchase-cost method."); await loadProductDetail(selected, variant.id); setTab("Variants");
    } catch (error) { setMessage(error instanceof Error ? error.message : "Could not save this pack size or option."); } finally { setBusy(false); }
  }

  async function toggleVariantStatus(variant: Variant) {
    setBusy(true);
    try { const updated = await updateVariant(variant.id, { status: variant.status === "ACTIVE" ? "INACTIVE" : "ACTIVE" }); setMessage(`Product option ${updated.status === "ACTIVE" ? "made available" : "made unavailable"}.`); if (selected) await loadProductDetail(selected, updated.id); }
    catch (error) { setMessage(error instanceof Error ? error.message : "Could not update this pack size or option."); } finally { setBusy(false); }
  }

  async function addBarcode(event: FormEvent) {
    event.preventDefault(); if (!selectedVariant || !barcode.trim()) return; setBusy(true);
    try { await createBarcode({ variant_id: selectedVariant.id, barcode: barcode.trim(), barcode_type: barcodeType, is_primary: barcodePrimary }); setBarcode(""); setBarcodePrimary(false); setMessage("Barcode added to the selected pack size or option."); await loadVariantDetail(selectedVariant); setTab("Barcodes"); }
    catch (error) { setMessage(error instanceof Error ? error.message : "Could not create the barcode."); } finally { setBusy(false); }
  }

  async function addPriceList(event: FormEvent) {
    event.preventDefault(); if (!priceListName.trim() || !effectiveFrom) return; setBusy(true);
    try { const created = await createPriceList({ name: priceListName.trim(), currency: priceListCurrency, price_type: priceListType, effective_from: iso(effectiveFrom) }); setPriceListName(""); setPriceListId(created.id); setMessage("Price list created. Now set prices for each pack size or option."); await loadCatalogReferences(); }
    catch (error) { setMessage(error instanceof Error ? error.message : "Could not create the price list."); } finally { setBusy(false); }
  }

  async function addPrice(event: FormEvent) {
    event.preventDefault(); if (!selectedVariant || !priceListId || !priceValue || !effectiveFrom) return; setBusy(true);
    try { await createPrice({ price_list_id: priceListId, variant_id: selectedVariant.id, unit_price: priceValue, minimum_quantity: minimumQuantity || "1", effective_from: iso(effectiveFrom) }); setPriceValue(""); setMinimumQuantity("1"); setMessage("Selling price saved to the selected price list."); await loadVariantDetail(selectedVariant); setTab("Pricing"); }
    catch (error) { setMessage(error instanceof Error ? error.message : "Could not create the price."); } finally { setBusy(false); }
  }

  return <AppShell title="Products" eyebrow="Products">
    <div className="module-toolbar"><div><strong>Products</strong><span>{catalogState === "loading" ? "Checking current products…" : catalogState === "error" ? "Products unavailable" : `${products.length} products · pack sizes, product codes, barcodes and prices`}</span>{referencesState === "error" && <small className="form-field-error">Some products reference data is unavailable; refresh before creating records.</small>}</div><div className="toolbar-actions"><button type="button" className="button button-soft" onClick={() => { void loadCatalog(); void loadCatalogReferences(); }} disabled={catalogState === "loading" || busy}>Refresh</button><button type="button" className="button button-dark" onClick={() => document.getElementById("new-product")?.scrollIntoView({behavior:"smooth"})}>+ New product</button></div></div>
    {message && <div className="notice">{message}</div>}

    <div className="workspace-grid">
      <section className="panel panel-wide"><div className="panel-head"><div><h2>Products</h2><p>Manage what your business sells or stocks, including pack sizes, product codes, barcodes and prices.</p></div><div className="table-search"><span>⌕</span><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search product name, product code or barcode" /></div></div>
        <ResponsiveDataTable
          rows={products}
          getKey={(product) => product.id}
          mobileTitle={(product) => product.name}
          mobileSubtitle={(product) => product.description || product.product_type}
          state={catalogState === "loading" ? "loading" : catalogState === "error" ? "error" : products.length ? "success" : "empty"}
          stateTitle={catalogState === "error" ? "Products could not be loaded" : catalogState === "loading" ? "Loading products" : "No products found"}
          stateDescription={catalogState === "error" ? "The latest products could not be confirmed. Retry before making changes." : catalogState === "loading" ? "Checking your saved product information." : "Add your first product or adjust your search."}
          onRetry={() => void loadCatalog()}
          onRowClick={(product) => void loadProductDetail(product)}
          emptyAction={<button type="button" className="button button-dark button-small" onClick={() => document.getElementById("new-product")?.scrollIntoView({ behavior: "smooth" })}>+ New product</button>}
          columns={[
            { key: "product", label: "Product", hideOnMobile: true, render: (product) => <><strong>{product.name}</strong><small>{product.description || product.product_type}</small></> },
            { key: "category", label: "Category", render: (product) => categoryMap.get(product.category_id) || "—" },
            { key: "brand", label: "Brand", render: (product) => brandMap.get(product.brand_id || "") || "—" },
            { key: "identity", label: "Pack sizes and options", render: (product) => product.has_variants ? "Has pack sizes or options" : "Single item" },
            { key: "status", label: "Status", render: (product) => <Badge variant={product.status === "ACTIVE" ? "success" : "neutral"}>{product.status === "ACTIVE" ? "Available" : "Not available"}</Badge> },
          ]}
        />
      </section>

      <aside className="panel detail-panel">{selected ? <>
        <div className="detail-kicker">PRODUCT</div><h2>{selected.name}</h2><p>{categoryMap.get(selected.category_id)||"Uncategorised"} · {brandMap.get(selected.brand_id||"")||"No brand"} · {selected.status === "ACTIVE" ? "Available" : "Not available"}</p>
        <div className="detail-stat"><span>Pack sizes and options</span><strong>{variants.length}</strong></div>
        <div className="module-tabs detail-tabs">{(["Overview","Variants","Pricing","Barcodes","Inventory"] as DetailTab[]).map(name=><button key={name} className={tab===name?"active":""} onClick={()=>setTab(name)}>{name === "Variants" ? "Pack sizes & options" : name === "Pricing" ? "Prices" : name}</button>)}</div>

        {tab==="Overview"&&<div className="detail-copy"><div className="detail-card"><span>DESCRIPTION</span><strong>{selected.description||"No description"}</strong></div><div className="detail-card"><span>HOW IT IS SOLD</span><strong>{selected.has_variants?"Has pack sizes or options":"Single item"}</strong></div><p className="detail-hint">Choose a pack size or option to manage its product code, barcode, selling price and stock.</p></div>}

        {tab==="Variants"&&<><div className="subsection"><div className="subsection-head"><strong>Pack sizes and options</strong></div>{variants.length?variants.map(variant=><button key={variant.id} className={`mini-row mini-row-button ${selectedVariant?.id===variant.id?"selected":""}`} onClick={()=>void loadVariantDetail(variant)}><div><strong>{variant.name}</strong><small>{variant.sku} · {unitMap.get(variant.base_unit_id)?.symbol||"unit"}</small></div><span>{variant.status === "ACTIVE" ? "Available" : "Not available"}</span></button>):<div className="empty-inline">No pack sizes or options have been added yet.</div>}</div>{selectedVariant&&<div className="detail-card"><span>PRODUCT CODE</span><strong>{selectedVariant.sku}</strong><small>{unitMap.get(selectedVariant.base_unit_id)?.name||"Base unit"} · {"Average purchase cost"}</small><button className="button button-soft button-small" onClick={()=>void toggleVariantStatus(selectedVariant)} disabled={busy}>{selectedVariant.status==="ACTIVE"?"Make unavailable":"Make available"} this option</button></div>}<form className="compact-form" onSubmit={addVariant}><h3>Add pack size or option</h3><input value={variantName} onChange={e=>setVariantName(e.target.value)} placeholder="Option name, e.g. 1 kg pack" required/><input value={sku} onChange={e=>setSku(e.target.value)} placeholder="Unique product code" required/><select value={unit} onChange={e=>setUnit(e.target.value)} required><option value="">Sold or stocked as</option>{units.map(item=><option key={item.id} value={item.id}>{item.name} ({item.symbol})</option>)}</select><select value={variantCosting} onChange={e=>setVariantCosting(e.target.value)}><option value="WEIGHTED_AVERAGE">Average purchase cost</option></select><button type="submit" className="button button-dark" disabled={busy}>Save option</button></form></>}

        {tab==="Barcodes"&&<><div className="subsection"><div className="subsection-head"><strong>{selectedVariant?selectedVariant.name:"Select a pack size or option"}</strong></div>{selectedVariant&&barcodes.length?barcodes.map(item=><div className="mini-row" key={item.id}><div><strong>{item.barcode}</strong><small>{item.barcode_type}</small></div><span>{item.is_primary?"Main barcode":"Available"}</span></div>):<div className="empty-inline">Select a pack size or option and add its first barcode.</div>}</div><form className="compact-form" onSubmit={addBarcode}><h3>Add barcode</h3><input value={barcode} onChange={e=>setBarcode(e.target.value)} placeholder="Scan or enter a barcode" inputMode="numeric" required disabled={!selectedVariant}/><select value={barcodeType} onChange={e=>setBarcodeType(e.target.value)} disabled={!selectedVariant}><option>EAN</option><option>UPC</option><option>CODE128</option><option>OTHER</option></select><label className="check-line"><input type="checkbox" checked={barcodePrimary} onChange={e=>setBarcodePrimary(e.target.checked)} disabled={!selectedVariant}/> Make primary barcode</label><button type="submit" className="button button-dark" disabled={busy||!selectedVariant}>Add barcode</button></form></>}

        {tab==="Pricing"&&<><div className="subsection"><div className="subsection-head"><strong>Current prices</strong></div>{selectedVariant&&prices.length?prices.map(item=>{const list=priceListMap.get(item.price_list_id);return <div className="mini-row" key={item.id}><div><strong>{money(item.unit_price,list?.currency||businessCurrency)}</strong><small>{list?.name||short(item.price_list_id)} · minimum quantity {item.minimum_quantity}</small></div><span>{new Date(item.effective_from).toLocaleDateString("en-GB")}</span></div>}):<div className="empty-inline">Select a pack size or option or add its first price.</div>}</div><form className="compact-form" onSubmit={addPrice}><h3>Set a selling price</h3><select value={priceListId} onChange={e=>setPriceListId(e.target.value)} disabled={!selectedVariant} required><option value="">Price list</option>{priceLists.map(list=><option key={list.id} value={list.id}>{list.name} · {list.currency}</option>)}</select><input type="number" min="0" step="0.01" value={priceValue} onChange={e=>setPriceValue(e.target.value)} placeholder="Selling price" required disabled={!selectedVariant}/><input type="number" min="0.001" step="0.001" value={minimumQuantity} onChange={e=>setMinimumQuantity(e.target.value)} placeholder="Minimum quantity for this price" required disabled={!selectedVariant}/><input type="datetime-local" value={effectiveFrom} onChange={e=>setEffectiveFrom(e.target.value)} required disabled={!selectedVariant}/><button type="submit" className="button button-dark" disabled={busy||!selectedVariant}>Save price</button></form></>}

        {tab==="Inventory"&&<div className="detail-copy">{!selectedVariant&&<div className="empty-inline">Select a pack size or option first.</div>}{selectedVariant&&!balances.length&&<div className="empty-inline">No stock record exists for this pack size or option yet.</div>}{balances.map(balance=><div className="detail-card" key={balance.id}><span>LOCATION {short(balance.location_id)}</span><strong>On hand {Number(balance.on_hand).toLocaleString("en-UG")} · Available {Number(balance.available).toLocaleString("en-UG")}</strong><small>{money(balance.stock_value,businessCurrency)} stock value · Avg. cost {money(balance.average_cost,businessCurrency)}</small></div>)}</div>}
      </>:<div className="detail-empty"><span>□</span><strong>Select a product</strong><p>Review pack sizes, barcodes, prices and stock without leaving Products.</p></div>}</aside>
    </div>

    <section id="new-product" className="panel form-panel"><div><div className="detail-kicker">PRODUCT SETUP</div><h2>New product</h2><p>Start with the product name. Add pack sizes or options, product codes, barcodes and selling prices.</p></div><form className="form-grid" onSubmit={addProduct}><label>Product name<input value={productName} onChange={e=>setProductName(e.target.value)} placeholder="e.g. Long Grain Rice" required/></label><label>Category<select value={category} onChange={e=>setCategory(e.target.value)} required><option value="">Select category</option>{categories.map(item=><option key={item.id} value={item.id}>{item.name}</option>)}</select></label><label>Brand<select value={brand} onChange={e=>setBrand(e.target.value)}><option value="">No brand</option>{brands.map(item=><option key={item.id} value={item.id}>{item.name}</option>)}</select></label><label>Description<input value={productDescription} onChange={e=>setProductDescription(e.target.value)} placeholder="Short operational description"/></label><div className="form-actions"><button type="submit" className="button button-dark" disabled={busy}>Create product</button></div></form></section>
    <section className="panel form-panel compact-section"><div><div className="detail-kicker">PRICE MANAGEMENT</div><h2>Price lists</h2><p>Create different prices for retail, wholesale or promotions.</p></div><form className="form-grid" onSubmit={addPriceList}><label>Name<input value={priceListName} onChange={e=>setPriceListName(e.target.value)} placeholder="Retail" required/></label><label>Type<select value={priceListType} onChange={e=>setPriceListType(e.target.value)}><option value="RETAIL">Retail</option><option value="WHOLESALE">Wholesale</option><option value="PROMO">Promotion</option><option value="TRADE">Trade</option></select></label><label>Currency<input value={priceListCurrency} onChange={e=>setPriceListCurrency(e.target.value.toUpperCase())} maxLength={3} required/></label><label>Price starts on<input type="datetime-local" value={effectiveFrom} onChange={e=>setEffectiveFrom(e.target.value)} required/></label><div className="form-actions"><button type="submit" className="button button-dark" disabled={busy}>Create price list</button></div></form><div className="price-list-strip">{priceLists.map(list=><button type="button" key={list.id} className={priceListId===list.id?"price-list-card selected":"price-list-card"} onClick={()=>setPriceListId(list.id)}><strong>{list.name}</strong><span>{({RETAIL:"Retail",WHOLESALE:"Wholesale",PROMO:"Promotion",TRADE:"Trade"} as Record<string,string>)[list.price_type] || "Price list"} · {list.currency}</span></button>)}</div></section>
  </AppShell>;
}
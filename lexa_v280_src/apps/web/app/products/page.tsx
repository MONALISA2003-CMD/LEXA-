"use client";

import { useEffect, useMemo, useState, type FormEvent } from "react";
import { AppShell } from "../../components/app-shell";
import {
  createBarcode, createPrice, createPriceList, createProduct, createVariant,
  getBarcodes, getBrands, getCategories, getInventoryBalances, getPriceLists,
  getPrices, getProducts, getUnits, getVariants, updateVariant,
  type Barcode, type Brand, type Category, type InventoryBalance,
  type PriceList, type Product, type ProductPrice, type Unit, type Variant,
} from "../../lib/api";

type DetailTab = "Overview" | "Variants" | "Pricing" | "Barcodes" | "Inventory";
function statusClass(status: string) { return status === "ACTIVE" ? "status-good" : "status-muted"; }
function money(value: string | number, currency = "UGX") { return new Intl.NumberFormat("en-UG", { style: "currency", currency, maximumFractionDigits: 0 }).format(Number(value)); }
function dateTimeInput() { const local = new Date(Date.now() - new Date().getTimezoneOffset() * 60000); return local.toISOString().slice(0, 16); }
function iso(value: string) { return new Date(value).toISOString(); }
function short(id: string) { return `${id.slice(0, 8)}…`; }

export default function ProductsPage() {
  const [products, setProducts] = useState<Product[]>([]), [categories, setCategories] = useState<Category[]>([]), [brands, setBrands] = useState<Brand[]>([]), [units, setUnits] = useState<Unit[]>([]), [priceLists, setPriceLists] = useState<PriceList[]>([]);
  const [variants, setVariants] = useState<Variant[]>([]), [selected, setSelected] = useState<Product | null>(null), [selectedVariant, setSelectedVariant] = useState<Variant | null>(null), [prices, setPrices] = useState<ProductPrice[]>([]), [barcodes, setBarcodes] = useState<Barcode[]>([]), [balances, setBalances] = useState<InventoryBalance[]>([]);
  const [tab, setTab] = useState<DetailTab>("Overview"), [search, setSearch] = useState(""), [busy, setBusy] = useState(true), [message, setMessage] = useState("");
  const [productName, setProductName] = useState(""), [productDescription, setProductDescription] = useState(""), [category, setCategory] = useState(""), [brand, setBrand] = useState("");
  const [variantName, setVariantName] = useState(""), [sku, setSku] = useState(""), [unit, setUnit] = useState(""), [variantCosting, setVariantCosting] = useState("WEIGHTED_AVERAGE");
  const [barcode, setBarcode] = useState(""), [barcodeType, setBarcodeType] = useState("EAN"), [barcodePrimary, setBarcodePrimary] = useState(false);
  const [priceListName, setPriceListName] = useState(""), [priceListType, setPriceListType] = useState("RETAIL"), [effectiveFrom, setEffectiveFrom] = useState(dateTimeInput()), [priceListCurrency, setPriceListCurrency] = useState("UGX"), [priceListId, setPriceListId] = useState(""), [priceValue, setPriceValue] = useState(""), [minimumQuantity, setMinimumQuantity] = useState("1");

  const categoryMap = useMemo(() => new Map(categories.map((x) => [x.id, x.name])), [categories]);
  const brandMap = useMemo(() => new Map(brands.map((x) => [x.id, x.name])), [brands]);
  const unitMap = useMemo(() => new Map(units.map((x) => [x.id, x])), [units]);
  const priceListMap = useMemo(() => new Map(priceLists.map((x) => [x.id, x])), [priceLists]);

  async function loadCatalog() {
    setBusy(true); setMessage("");
    try {
      const [p, c, b, u, pl] = await Promise.all([getProducts(search), getCategories(), getBrands(), getUnits(), getPriceLists()]);
      setProducts(p.items); setCategories(c.items); setBrands(b.items); setUnits(u.items); setPriceLists(pl);
      if (!category && c.items[0]) setCategory(c.items[0].id); if (!unit && u.items[0]) setUnit(u.items[0].id); if (!priceListId && pl[0]) setPriceListId(pl[0].id);
    } catch (error) { setMessage(error instanceof Error ? error.message : "Unable to load the product catalogue."); }
    finally { setBusy(false); }
  }

  useEffect(() => { const timer = setTimeout(() => void loadCatalog(), 250); return () => clearTimeout(timer); }, [search]);
  useEffect(() => {
    const query = new URLSearchParams(window.location.search).get("q");
    if (query) setSearch(query);
  }, []);

  async function loadVariantDetail(variant: Variant) {
    setSelectedVariant(variant);
    try {
      const [nextPrices, nextBarcodes, nextBalances] = await Promise.all([getPrices({ variant_id: variant.id }), getBarcodes(variant.id), getInventoryBalances({ variant_id: variant.id })]);
      setPrices(nextPrices); setBarcodes(nextBarcodes); setBalances(nextBalances);
    } catch (error) { setMessage(error instanceof Error ? error.message : "Unable to load variant details."); }
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
      setProductName(""); setProductDescription(""); setMessage("Product created. Add a sellable variant to complete its commercial identity."); await loadCatalog(); await loadProductDetail(product);
    } catch (error) { setMessage(error instanceof Error ? error.message : "Could not create the product."); } finally { setBusy(false); }
  }

  async function addVariant(event: FormEvent) {
    event.preventDefault(); if (!selected || !variantName.trim() || !sku.trim() || !unit) return; setBusy(true);
    try {
      const variant = await createVariant({ product_id: selected.id, name: variantName.trim(), sku: sku.trim().toUpperCase(), base_unit_id: unit, costing_method: variantCosting });
      setVariantName(""); setSku(""); setMessage("Variant created with its own SKU and costing policy."); await loadProductDetail(selected, variant.id); setTab("Variants");
    } catch (error) { setMessage(error instanceof Error ? error.message : "Could not create the variant."); } finally { setBusy(false); }
  }

  async function toggleVariantStatus(variant: Variant) {
    setBusy(true);
    try { const updated = await updateVariant(variant.id, { status: variant.status === "ACTIVE" ? "INACTIVE" : "ACTIVE" }); setMessage(`Variant ${updated.status === "ACTIVE" ? "activated" : "deactivated"}.`); if (selected) await loadProductDetail(selected, updated.id); }
    catch (error) { setMessage(error instanceof Error ? error.message : "Could not update the variant."); } finally { setBusy(false); }
  }

  async function addBarcode(event: FormEvent) {
    event.preventDefault(); if (!selectedVariant || !barcode.trim()) return; setBusy(true);
    try { await createBarcode({ variant_id: selectedVariant.id, barcode: barcode.trim(), barcode_type: barcodeType, is_primary: barcodePrimary }); setBarcode(""); setBarcodePrimary(false); setMessage("Barcode added to the selected variant."); await loadVariantDetail(selectedVariant); setTab("Barcodes"); }
    catch (error) { setMessage(error instanceof Error ? error.message : "Could not create the barcode."); } finally { setBusy(false); }
  }

  async function addPriceList(event: FormEvent) {
    event.preventDefault(); if (!priceListName.trim() || !effectiveFrom) return; setBusy(true);
    try { const created = await createPriceList({ name: priceListName.trim(), currency: priceListCurrency, price_type: priceListType, effective_from: iso(effectiveFrom) }); setPriceListName(""); setPriceListId(created.id); setMessage("Price list created. Now attach prices to sellable variants."); await loadCatalog(); }
    catch (error) { setMessage(error instanceof Error ? error.message : "Could not create the price list."); } finally { setBusy(false); }
  }

  async function addPrice(event: FormEvent) {
    event.preventDefault(); if (!selectedVariant || !priceListId || !priceValue || !effectiveFrom) return; setBusy(true);
    try { await createPrice({ price_list_id: priceListId, variant_id: selectedVariant.id, unit_price: priceValue, minimum_quantity: minimumQuantity || "1", effective_from: iso(effectiveFrom) }); setPriceValue(""); setMinimumQuantity("1"); setMessage("Price published to the selected price list."); await loadVariantDetail(selectedVariant); setTab("Pricing"); }
    catch (error) { setMessage(error instanceof Error ? error.message : "Could not create the price."); } finally { setBusy(false); }
  }

  return <AppShell title="Products" eyebrow="Catalog">
    <div className="module-toolbar"><div><strong>Product catalogue</strong><span>{products.length} visible products · structured SKU, barcode and pricing identity</span></div><button className="button button-dark" onClick={() => document.getElementById("new-product")?.scrollIntoView({behavior:"smooth"})}>+ New product</button></div>
    {message && <div className="notice">{message}</div>}

    <div className="workspace-grid">
      <section className="panel panel-wide"><div className="panel-head"><div><h2>Products</h2><p>Product records describe what the business sells or stocks. Sellable identity lives in variants.</p></div><div className="table-search"><span>⌕</span><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search product, SKU or barcode" /></div></div>
        <div className="data-table-wrap"><table className="data-table"><thead><tr><th>Product</th><th>Category</th><th>Brand</th><th>Identity</th><th>Status</th><th /></tr></thead><tbody>
          {products.map((product) => <tr key={product.id} className={selected?.id===product.id?"selected-row":""} onClick={() => void loadProductDetail(product)}><td><strong>{product.name}</strong><small>{product.description||product.product_type}</small></td><td>{categoryMap.get(product.category_id)||"—"}</td><td>{brandMap.get(product.brand_id||"")||"—"}</td><td>{product.has_variants?"Variant-based":"Single item"}</td><td><span className={`status-pill ${statusClass(product.status)}`}>{product.status}</span></td><td>›</td></tr>)}
          {busy&&!products.length&&<tr><td colSpan={6}><div className="loading-placeholder">Loading authoritative catalogue…</div></td></tr>}
          {!products.length&&!busy&&<tr><td colSpan={6}><div className="empty-state"><strong>No products found</strong><span>Create the first catalogue record or refine the search.</span></div></td></tr>}
        </tbody></table></div>
      </section>

      <aside className="panel detail-panel">{selected ? <>
        <div className="detail-kicker">PRODUCT</div><h2>{selected.name}</h2><p>{categoryMap.get(selected.category_id)||"Uncategorised"} · {brandMap.get(selected.brand_id||"")||"No brand"} · {selected.status}</p>
        <div className="detail-stat"><span>Variants</span><strong>{variants.length}</strong></div>
        <div className="module-tabs detail-tabs">{(["Overview","Variants","Pricing","Barcodes","Inventory"] as DetailTab[]).map(name=><button key={name} className={tab===name?"active":""} onClick={()=>setTab(name)}>{name}</button>)}</div>

        {tab==="Overview"&&<div className="detail-copy"><div className="detail-card"><span>DESCRIPTION</span><strong>{selected.description||"No description"}</strong></div><div className="detail-card"><span>CATALOGUE ID</span><strong>{short(selected.id)}</strong></div><div className="detail-card"><span>SELLABLE MODEL</span><strong>{selected.has_variants?"Variant-based":"Single item"}</strong></div><p className="detail-hint">Select a variant to manage its SKU, barcode, price and inventory identity.</p></div>}

        {tab==="Variants"&&<><div className="subsection"><div className="subsection-head"><strong>Sellable variants</strong></div>{variants.length?variants.map(variant=><button key={variant.id} className={`mini-row mini-row-button ${selectedVariant?.id===variant.id?"selected":""}`} onClick={()=>void loadVariantDetail(variant)}><div><strong>{variant.name}</strong><small>{variant.sku} · {unitMap.get(variant.base_unit_id)?.symbol||"unit"}</small></div><span>{variant.status}</span></button>):<div className="empty-inline">No variants yet.</div>}</div>{selectedVariant&&<div className="detail-card"><span>SELECTED SKU</span><strong>{selectedVariant.sku}</strong><small>{unitMap.get(selectedVariant.base_unit_id)?.name||"Base unit"} · {selectedVariant.costing_method||"WEIGHTED_AVERAGE"}</small><button className="button button-soft button-small" onClick={()=>void toggleVariantStatus(selectedVariant)} disabled={busy}>{selectedVariant.status==="ACTIVE"?"Deactivate":"Activate"} variant</button></div>}<form className="compact-form" onSubmit={addVariant}><h3>Add variant</h3><input value={variantName} onChange={e=>setVariantName(e.target.value)} placeholder="Variant name" required/><input value={sku} onChange={e=>setSku(e.target.value)} placeholder="Unique SKU" required/><select value={unit} onChange={e=>setUnit(e.target.value)} required><option value="">Base unit</option>{units.map(item=><option key={item.id} value={item.id}>{item.name} ({item.symbol})</option>)}</select><select value={variantCosting} onChange={e=>setVariantCosting(e.target.value)}><option value="WEIGHTED_AVERAGE">Weighted average costing</option></select><button className="button button-dark" disabled={busy}>Create variant</button></form></>}

        {tab==="Barcodes"&&<><div className="subsection"><div className="subsection-head"><strong>{selectedVariant?selectedVariant.name:"Select a variant"}</strong></div>{selectedVariant&&barcodes.length?barcodes.map(item=><div className="mini-row" key={item.id}><div><strong>{item.barcode}</strong><small>{item.barcode_type}</small></div><span>{item.is_primary?"PRIMARY":"ACTIVE"}</span></div>):<div className="empty-inline">Select a variant and add its first barcode.</div>}</div><form className="compact-form" onSubmit={addBarcode}><h3>Add barcode</h3><input value={barcode} onChange={e=>setBarcode(e.target.value)} placeholder="Scan or enter barcode" inputMode="numeric" required disabled={!selectedVariant}/><select value={barcodeType} onChange={e=>setBarcodeType(e.target.value)} disabled={!selectedVariant}><option>EAN</option><option>UPC</option><option>CODE128</option><option>OTHER</option></select><label className="check-line"><input type="checkbox" checked={barcodePrimary} onChange={e=>setBarcodePrimary(e.target.checked)} disabled={!selectedVariant}/> Make primary barcode</label><button className="button button-dark" disabled={busy||!selectedVariant}>Add barcode</button></form></>}

        {tab==="Pricing"&&<><div className="subsection"><div className="subsection-head"><strong>Effective prices</strong></div>{selectedVariant&&prices.length?prices.map(item=>{const list=priceListMap.get(item.price_list_id);return <div className="mini-row" key={item.id}><div><strong>{money(item.unit_price,list?.currency||"UGX")}</strong><small>{list?.name||short(item.price_list_id)} · min {item.minimum_quantity}</small></div><span>{new Date(item.effective_from).toLocaleDateString("en-GB")}</span></div>}):<div className="empty-inline">Select a variant or publish its first price.</div>}</div><form className="compact-form" onSubmit={addPrice}><h3>Publish variant price</h3><select value={priceListId} onChange={e=>setPriceListId(e.target.value)} disabled={!selectedVariant} required><option value="">Price list</option>{priceLists.map(list=><option key={list.id} value={list.id}>{list.name} · {list.currency}</option>)}</select><input type="number" min="0" step="0.01" value={priceValue} onChange={e=>setPriceValue(e.target.value)} placeholder="Unit price" required disabled={!selectedVariant}/><input type="number" min="0.001" step="0.001" value={minimumQuantity} onChange={e=>setMinimumQuantity(e.target.value)} placeholder="Minimum quantity" required disabled={!selectedVariant}/><input type="datetime-local" value={effectiveFrom} onChange={e=>setEffectiveFrom(e.target.value)} required disabled={!selectedVariant}/><button className="button button-dark" disabled={busy||!selectedVariant}>Publish price</button></form></>}

        {tab==="Inventory"&&<div className="detail-copy">{!selectedVariant&&<div className="empty-inline">Select a variant first.</div>}{selectedVariant&&!balances.length&&<div className="empty-inline">No balance rows exist for this variant yet.</div>}{balances.map(balance=><div className="detail-card" key={balance.id}><span>LOCATION {short(balance.location_id)}</span><strong>On hand {Number(balance.on_hand).toLocaleString("en-UG")} · Available {Number(balance.available).toLocaleString("en-UG")}</strong><small>{money(balance.stock_value)} stock value · Avg. cost {money(balance.average_cost)}</small></div>)}</div>}
      </>:<div className="detail-empty"><span>□</span><strong>Select a product</strong><p>Review variants, barcode identity, pricing and inventory without leaving the catalogue.</p></div>}</aside>
    </div>

    <section id="new-product" className="panel form-panel"><div><div className="detail-kicker">CATALOGUE SETUP</div><h2>New product</h2><p>Start with the product concept. Add SKU, barcode and pricing at the variant level.</p></div><form className="form-grid" onSubmit={addProduct}><label>Product name<input value={productName} onChange={e=>setProductName(e.target.value)} placeholder="e.g. Long Grain Rice" required/></label><label>Category<select value={category} onChange={e=>setCategory(e.target.value)} required><option value="">Select category</option>{categories.map(item=><option key={item.id} value={item.id}>{item.name}</option>)}</select></label><label>Brand<select value={brand} onChange={e=>setBrand(e.target.value)}><option value="">No brand</option>{brands.map(item=><option key={item.id} value={item.id}>{item.name}</option>)}</select></label><label>Description<input value={productDescription} onChange={e=>setProductDescription(e.target.value)} placeholder="Short operational description"/></label><div className="form-actions"><button className="button button-dark" disabled={busy}>Create product</button></div></form></section>
    <section className="panel form-panel compact-section"><div><div className="detail-kicker">PRICE MANAGEMENT</div><h2>Price lists</h2><p>Named commercial contexts with effective-dated prices.</p></div><form className="form-grid" onSubmit={addPriceList}><label>Name<input value={priceListName} onChange={e=>setPriceListName(e.target.value)} placeholder="Retail" required/></label><label>Type<select value={priceListType} onChange={e=>setPriceListType(e.target.value)}><option>RETAIL</option><option>WHOLESALE</option><option>PROMO</option><option>TRADE</option></select></label><label>Currency<input value={priceListCurrency} onChange={e=>setPriceListCurrency(e.target.value.toUpperCase())} maxLength={3} required/></label><label>Effective from<input type="datetime-local" value={effectiveFrom} onChange={e=>setEffectiveFrom(e.target.value)} required/></label><div className="form-actions"><button className="button button-dark" disabled={busy}>Create price list</button></div></form><div className="price-list-strip">{priceLists.map(list=><button type="button" key={list.id} className={priceListId===list.id?"price-list-card selected":"price-list-card"} onClick={()=>setPriceListId(list.id)}><strong>{list.name}</strong><span>{list.price_type} · {list.currency}</span></button>)}</div></section>
  </AppShell>;
}
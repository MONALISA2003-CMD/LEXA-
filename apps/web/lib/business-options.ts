/** Common business locations and currencies exposed by the LEXA setup UI. */
export const BUSINESS_COUNTRIES = [
  { code: "UG", name: "Uganda" }, { code: "KE", name: "Kenya" },
  { code: "TZ", name: "Tanzania" }, { code: "RW", name: "Rwanda" },
  { code: "SS", name: "South Sudan" }, { code: "US", name: "United States" },
  { code: "GB", name: "United Kingdom" }, { code: "ZA", name: "South Africa" },
  { code: "NG", name: "Nigeria" }, { code: "GH", name: "Ghana" },
  { code: "IN", name: "India" }, { code: "AE", name: "United Arab Emirates" },
] as const;

export const BUSINESS_CURRENCIES = [
  { code: "UGX", name: "Ugandan shilling" }, { code: "KES", name: "Kenyan shilling" },
  { code: "TZS", name: "Tanzanian shilling" }, { code: "RWF", name: "Rwandan franc" },
  { code: "SSP", name: "South Sudanese pound" }, { code: "USD", name: "US dollar" },
  { code: "GBP", name: "British pound" }, { code: "EUR", name: "Euro" },
  { code: "ZAR", name: "South African rand" }, { code: "NGN", name: "Nigerian naira" },
  { code: "GHS", name: "Ghanaian cedi" }, { code: "INR", name: "Indian rupee" },
  { code: "AED", name: "UAE dirham" },
] as const;

export function isValidBusinessCurrency(value: unknown): value is string {
  return typeof value === "string" && /^[A-Z]{3}$/.test(value.trim().toUpperCase());
}

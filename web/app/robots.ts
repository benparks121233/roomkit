import type { MetadataRoute } from "next";

export default function robots(): MetadataRoute.Robots {
  return {
    rules: {
      userAgent: "*",
      disallow: ["/admin", "/preview", "/auth", "/reset-password", "/forgot-password", "/account"],
    },
  };
}

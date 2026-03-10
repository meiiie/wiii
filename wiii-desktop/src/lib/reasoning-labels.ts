/**
 * Shared label mappings for the reasoning rail components.
 * Extracted from ThinkingBlock + ToolExecutionStrip + ActionText
 * to eliminate duplication (WAVE-004).
 */

/** Vietnamese labels for tool names used across reasoning UI. */
export const TOOL_LABELS: Record<string, string> = {
  tool_knowledge_search: "Tra cuu kien thuc",
  tool_maritime_search: "Tra cuu hang hai",
  tool_web_search: "Tim kiem web",
  tool_search_news: "Tim tin tuc",
  tool_search_legal: "Tra cuu phap luat",
  tool_search_maritime: "Tim kiem hang hai",
  tool_current_datetime: "Thoi gian hien tai",
  tool_calculator: "May tinh",
  tool_think: "Suy nghi",
  tool_save_user_info: "Luu thong tin",
  tool_get_user_info: "Truy xuat thong tin",
  tool_execute_python: "Chay ma Python",
  tool_browser_snapshot_url: "Mo trang va chup nhanh",
  tool_generate_html_file: "Tao HTML",
  tool_generate_excel_file: "Tao Excel",
  tool_generate_word_document: "Tao Word",
};

/** Vietnamese labels for agent node names. */
export const NODE_LABELS: Record<string, string> = {
  supervisor: "Dieu huong",
  rag: "Tra cuu",
  rag_agent: "Tra cuu",
  tutor: "Giai thich",
  tutor_agent: "Giai thich",
  memory: "Tri nho",
  direct: "Truc tiep",
  grader: "Danh gia",
  guardian: "Kiem duyet",
  synthesizer: "Tong hop",
  search: "Doi chieu",
  product_search: "Tim san pham",
  product_search_agent: "Doi chieu",
  web_search: "Tim web",
  aggregator: "Hop nhat",
  parallel_dispatch: "Song song",
};

/** Vietnamese labels for reasoning phases. */
export const PHASE_LABELS: Record<string, string> = {
  attune: "Bat nhip",
  clarify: "Lam ro",
  ground: "Kiem du lieu",
  verify: "Kiem cheo",
  counterpoint: "Phan bien",
  decision: "Chon huong",
  synthesis: "Chot lai",
};

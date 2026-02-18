# UX Design: Article Reader

## User Flows

### Flow 1: Accessing an Article
1.  User views the **Weekly Report** (or Index page).
2.  User sees an interesting headline in the list.
3.  User notices two links: The main headline (links to Source) and a "Reader View" icon/text.
4.  User clicks **"Reader View"**.
5.  System opens the static article page in the same tab (or new tab, depending on preference).
6.  User reads the article.
7.  User clicks **"← Back to Report"** at the top left.
8.  System returns user to the Weekly Report.

## UI States

### Link Component (in Weekly Report)
-   **Default**: Display "Reader View" (or a document icon) next to the source link.
-   **Hover**: Tooltip "Read locally".

### Reader Page (`article_template.j2`)
-   **Header**:
    -   "← Back" link.
    -   "Original Source" external link icon.
-   **Content**:
    -   **Title**: H1, bold, large.
    -   **Metadata**: Grey text (Date, Site Name).
    -   **Body**: Serif font (or clean Sans), 1.6 line height, max-width ~700px for readability.
-   **Loading**: N/A (Static HTML).
-   **Error**: 404 if file missing (standard browser error).

## Copy Dictionary
| Key | Text | Context |
|-----|------|---------|
| `link_reader` | "Reader View" | Secondary link in report list |
| `nav_back` | "← Back to Report" | Top navigation in Reader View |
| `meta_original`| "View Original Source" | Link to external site |

## Accessibility
-   **Semantic HTML**: Use `<article>`, `<h1>`, `<p>` tags correctly.
-   **Contrast**: Dark grey text on off-white background (#333 on #FAFAFA).
-   **Scalability**: Use `rem` units for font sizes to respect user defaults.

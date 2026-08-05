/* =========================
   同じカテゴリのツール一覧
========================= */

const currentTool = TOOLS.find(t => t.id === CURRENT_TOOL);

const container = document.getElementById("related-tools");

if (currentTool && container) {

  const relatedTools = TOOLS.filter(
    t => !t.hidden
      && t.category === currentTool.category
      && t.id !== currentTool.id
  );

  if (relatedTools.length > 0) {

    container.innerHTML = `

      <section class="related-tools-section">
        <h2>同じカテゴリのツール</h2>

        <div class="related-tools-grid">

          ${relatedTools.map(tool => `

            <a href="${tool.url}" class="related-tool-card">
              <h3>${tool.title}</h3>
              <p>${tool.desc}</p>
            </a>

          `).join("")}

        </div>
      </section>

    `;
  }
}

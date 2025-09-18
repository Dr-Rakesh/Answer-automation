document.getElementById("uploadForm").addEventListener("submit", async function (event) {
  event.preventDefault();

  const product = document.getElementById("product").value;
  const version = document.getElementById("version").value;
  const fileInput = document.getElementById("fileInput");
  const spinner = document.getElementById("loadingSpinner");
  const downloadLink = document.getElementById("downloadLink");
  const downloadAnchor = document.getElementById("downloadAnchor");

  spinner.style.display = "block";
  downloadLink.style.display = "none";

  if (!fileInput.files.length) {
    alert("Please select a file to upload.");
    spinner.style.display = "none";
    return;
  }

  const formData = new FormData();
  formData.append("product", product);
  formData.append("version", version);
  formData.append("file", fileInput.files[0]);

  try {
    const response = await fetch("/upload-file/", {
      method: "POST",
      body: formData,
    });

    if (response.ok) {
      const blob = await response.blob();
      const downloadURL = window.URL.createObjectURL(blob);
      downloadAnchor.href = downloadURL;
      downloadAnchor.download = fileInput.files[0].name.replace(/\.[^/.]+$/, "_processed$&");
      downloadLink.style.display = "block";
    } else {
      alert("Error processing file. Please try again.");
    }
  } catch (error) {
    alert("An error occurred while processing the file.");
    console.error(error);
  } finally {
    spinner.style.display = "none";
  }
});
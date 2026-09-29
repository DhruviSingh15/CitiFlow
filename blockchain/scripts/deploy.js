const hre = require("hardhat");
const fs  = require("fs");
const path = require("path");

async function main() {
  console.log("Deploying CrossBorderSettlement...");

  const [deployer] = await hre.ethers.getSigners();
  console.log("Deploying with account:", deployer.address);
  console.log("Account balance:", (await deployer.provider.getBalance(deployer.address)).toString());

  const Contract = await hre.ethers.getContractFactory("CrossBorderSettlement");
  const contract = await Contract.deploy();
  await contract.waitForDeployment();

  const address = await contract.getAddress();
  console.log("CrossBorderSettlement deployed to:", address);

  // Write address to a JSON file for the backend to read
  const deployInfo = {
    address,
    network:    hre.network.name,
    deployedAt: new Date().toISOString(),
    deployer:   deployer.address,
  };

  const outPath = path.join(__dirname, "../deploy_info.json");
  fs.writeFileSync(outPath, JSON.stringify(deployInfo, null, 2));
  console.log("Deploy info written to:", outPath);

  // Also print the backend .env update needed
  console.log("\n--- Update your backend/.env ---");
  console.log(`CONTRACT_ADDRESS=${address}`);
  console.log("--------------------------------");
}

main()
  .then(() => process.exit(0))
  .catch((err) => { console.error(err); process.exit(1); });
